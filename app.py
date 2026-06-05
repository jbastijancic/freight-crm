from flask import Flask, render_template, request, redirect, url_for, Response
import csv
import io
import json
import os
import sys
from pathlib import Path
from datetime import date

# ── Path resolution (dev / PyInstaller / cloud) ───────────────────────────────
if getattr(sys, "frozen", False):
    _RESOURCE_DIR = Path(sys._MEIPASS)
    _DATA_DIR     = Path(sys.executable).parent
else:
    _RESOURCE_DIR = Path(__file__).parent
    _DATA_DIR     = Path(__file__).parent

CONFIG_FILE = _DATA_DIR / "config.json"

# ── Flask setup ───────────────────────────────────────────────────────────────
app = Flask(__name__,
    template_folder=str(_RESOURCE_DIR / "templates"),
    static_folder=str(_RESOURCE_DIR / "static"),
)

# ── Database ──────────────────────────────────────────────────────────────────
_DB_PATH     = _DATA_DIR / "crm.db"
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DB_PATH}")
# Railway provides postgres://, SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"]        = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from models import db, Contact, Note, Shipment
db.init_app(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def next_contact_id():
    prefix   = load_config()["id_prefixes"]["contact"]
    existing = Contact.query.filter(Contact.id.like(f"{prefix}%")).all()
    nums     = [int(c.id.replace(prefix, "")) for c in existing]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"

def next_shipment_id():
    prefix   = load_config()["id_prefixes"]["shipment"]
    existing = Shipment.query.filter(Shipment.id.like(f"{prefix}%")).all()
    nums     = [int(s.id.replace(prefix, "")) for s in existing]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"

def get_names():
    return {c.id: c.name for c in Contact.query.all()}


# ── Auto-migrate from JSON on first run ───────────────────────────────────────

def migrate_from_json():
    """Import existing JSON files into the database — runs once on first startup."""
    if Contact.query.count() > 0:
        return

    contacts_file  = _DATA_DIR / "contacts.json"
    shipments_file = _DATA_DIR / "shipments.json"

    if contacts_file.exists():
        with open(contacts_file) as f:
            raw = json.load(f)
        for c in raw.get("contacts", []):
            db.session.add(Contact(
                id=c["id"], type=c["type"], name=c["name"],
                company=c.get("company", ""), phone=c.get("phone", ""),
                email=c.get("email", ""), address=c.get("address", ""),
                active=c.get("active", True), created_at=c.get("created_at", ""),
            ))
            for n in c.get("notes", []):
                db.session.add(Note(
                    contact_id=c["id"],
                    date=n["date"] if isinstance(n, dict) else c.get("created_at", ""),
                    text=n["text"] if isinstance(n, dict) else str(n),
                ))

    if shipments_file.exists():
        with open(shipments_file) as f:
            raw = json.load(f)
        for s in raw.get("shipments", []):
            db.session.add(Shipment(
                id=s["id"], status=s["status"],
                customer_id=s.get("customer_id", ""),
                carrier_id=s.get("carrier_id", ""),
                origin=s.get("origin", ""), destination=s.get("destination", ""),
                pickup_date=s.get("pickup_date", ""),
                delivery_date=s.get("delivery_date", ""),
                rate=s.get("rate", 0.0), commodity=s.get("commodity", ""),
                weight_lbs=s.get("weight_lbs", 0), notes=s.get("notes", ""),
            ))

    db.session.commit()
    print("Imported existing data from JSON into database.")


# ── Init DB on startup ────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    migrate_from_json()


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    config          = load_config()
    total_contacts  = Contact.query.count()
    total_shipments = Shipment.query.count()
    in_transit      = Shipment.query.filter_by(status="in_transit").count()
    total_revenue   = db.session.query(db.func.sum(Shipment.rate)).filter(
                          Shipment.status != "cancelled").scalar() or 0
    recent          = Shipment.query.order_by(Shipment.pickup_date.desc()).limit(5).all()
    return render_template("dashboard.html",
        config=config, total_contacts=total_contacts,
        total_shipments=total_shipments, in_transit=in_transit,
        total_revenue=total_revenue, recent=recent, names=get_names())


# ── Contacts ──────────────────────────────────────────────────────────────────

@app.route("/contacts")
def contacts_list():
    config      = load_config()
    q           = request.args.get("q", "").lower()
    type_filter = request.args.get("type", "")

    query    = Contact.query
    if type_filter:
        query = query.filter_by(type=type_filter)
    contacts = query.all()

    if q:
        contacts = [c for c in contacts if
            q in (c.name    or "").lower() or
            q in (c.company or "").lower() or
            q in (c.email   or "").lower()
        ]
    return render_template("contacts.html",
        contacts=contacts, config=config, q=q, type_filter=type_filter)


@app.route("/contacts/new", methods=["GET", "POST"])
def contact_new():
    config = load_config()
    if request.method == "POST":
        contact = Contact(
            id=next_contact_id(),
            type=request.form["type"],
            name=request.form["name"],
            company=request.form.get("company", ""),
            phone=request.form.get("phone", ""),
            email=request.form.get("email", ""),
            address=request.form.get("address", ""),
            created_at=date.today().isoformat(),
            active=True,
        )
        db.session.add(contact)
        note_text = request.form.get("note", "").strip()
        if note_text:
            db.session.add(Note(contact_id=contact.id,
                                date=date.today().isoformat(), text=note_text))
        db.session.commit()
        return redirect(url_for("contact_detail", contact_id=contact.id))
    return render_template("contact_form.html", config=config, contact=None)


@app.route("/contacts/<contact_id>")
def contact_detail(contact_id):
    contact = db.session.get(Contact, contact_id) or (None, 404)[1]
    if not contact:
        return "Contact not found", 404
    related = Shipment.query.filter(
        (Shipment.customer_id == contact_id) | (Shipment.carrier_id == contact_id)
    ).all()
    return render_template("contact_detail.html",
        contact=contact, related=related, names=get_names(), config=load_config())


@app.route("/contacts/<contact_id>/edit", methods=["GET", "POST"])
def contact_edit(contact_id):
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return "Contact not found", 404
    config = load_config()
    if request.method == "POST":
        contact.type    = request.form.get("type",    contact.type)
        contact.name    = request.form.get("name",    contact.name)
        contact.company = request.form.get("company", "")
        contact.phone   = request.form.get("phone",   "")
        contact.email   = request.form.get("email",   "")
        contact.address = request.form.get("address", "")
        contact.active  = request.form.get("active") == "on"
        new_note = request.form.get("new_note", "").strip()
        if new_note:
            db.session.add(Note(contact_id=contact_id,
                                date=date.today().isoformat(), text=new_note))
        db.session.commit()
        return redirect(url_for("contact_detail", contact_id=contact_id))
    return render_template("contact_form.html", config=config, contact=contact)


# ── Shipments ─────────────────────────────────────────────────────────────────

@app.route("/shipments")
def shipments_list():
    config        = load_config()
    status_filter = request.args.get("status", "")
    query         = Shipment.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    shipments = query.order_by(Shipment.pickup_date.desc()).all()
    return render_template("shipments.html",
        shipments=shipments, names=get_names(), config=config,
        status_filter=status_filter)


@app.route("/shipments/new", methods=["GET", "POST"])
def shipment_new():
    contacts = Contact.query.all()
    config   = load_config()
    if request.method == "POST":
        rate_str   = request.form.get("rate", "")
        weight_str = request.form.get("weight_lbs", "")
        shipment   = Shipment(
            id=next_shipment_id(),
            status=request.form.get("status", "booked"),
            customer_id=request.form.get("customer_id", ""),
            carrier_id=request.form.get("carrier_id", ""),
            origin=request.form.get("origin", ""),
            destination=request.form.get("destination", ""),
            pickup_date=request.form.get("pickup_date", ""),
            delivery_date=request.form.get("delivery_date", ""),
            rate=float(rate_str) if rate_str else 0.0,
            commodity=request.form.get("commodity", ""),
            weight_lbs=int(weight_str) if weight_str else 0,
            notes=request.form.get("notes", ""),
        )
        db.session.add(shipment)
        db.session.commit()
        return redirect(url_for("shipment_detail", shipment_id=shipment.id))
    return render_template("shipment_form.html", contacts=contacts, config=config)


@app.route("/shipments/<shipment_id>")
def shipment_detail(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if not shipment:
        return "Shipment not found", 404
    return render_template("shipment_detail.html",
        shipment=shipment, names=get_names(), config=load_config())


@app.route("/shipments/<shipment_id>/status", methods=["POST"])
def shipment_status(shipment_id):
    shipment = db.session.get(Shipment, shipment_id)
    if shipment:
        shipment.status = request.form["status"]
        db.session.commit()
    return redirect(url_for("shipment_detail", shipment_id=shipment_id))


# ── Report ────────────────────────────────────────────────────────────────────

@app.route("/report")
def report():
    config  = load_config()
    names   = get_names()
    billed  = Shipment.query.filter(
        Shipment.rate > 0, Shipment.status != "cancelled").all()

    total_revenue = sum(s.rate for s in billed)
    avg_rate      = total_revenue / len(billed) if billed else 0

    by_customer = {}
    for s in billed:
        name = names.get(s.customer_id, "Unknown")
        by_customer.setdefault(name, {"count": 0, "total": 0.0})
        by_customer[name]["count"] += 1
        by_customer[name]["total"] += s.rate

    by_carrier = {}
    for s in billed:
        if not s.carrier_id:
            continue
        name = names.get(s.carrier_id, s.carrier_id)
        by_carrier.setdefault(name, {"count": 0, "total": 0.0})
        by_carrier[name]["count"] += 1
        by_carrier[name]["total"] += s.rate

    return render_template("report.html",
        config=config, billed=billed,
        by_customer=dict(sorted(by_customer.items(), key=lambda x: -x[1]["total"])),
        by_carrier=dict(sorted(by_carrier.items(),   key=lambda x: -x[1]["total"])),
        total_revenue=total_revenue, avg_rate=avg_rate, total_shipments=len(billed))


# ── CSV Exports ───────────────────────────────────────────────────────────────

@app.route("/export/contacts")
def export_contacts():
    contacts = Contact.query.order_by(Contact.id).all()
    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(["ID","Type","Name","Company","Phone","Email","Address","Active","Created"])
    for c in contacts:
        w.writerow([c.id, c.type, c.name, c.company, c.phone, c.email,
                    c.address, "Yes" if c.active else "No", c.created_at])
    return Response(out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"})


@app.route("/export/shipments")
def export_shipments():
    shipments = Shipment.query.order_by(Shipment.pickup_date.desc()).all()
    names = get_names()
    out   = io.StringIO()
    w     = csv.writer(out)
    w.writerow(["ID","Status","Customer","Carrier","Origin","Destination",
                "Pickup Date","Delivery Date","Rate (USD)","Commodity","Weight (lbs)","Notes"])
    for s in shipments:
        w.writerow([
            s.id, s.status,
            names.get(s.customer_id, s.customer_id),
            names.get(s.carrier_id,  s.carrier_id) if s.carrier_id else "",
            s.origin, s.destination, s.pickup_date, s.delivery_date,
            s.rate, s.commodity, s.weight_lbs, s.notes,
        ])
    return Response(out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=shipments.csv"})


@app.route("/export/report")
def export_report():
    names  = get_names()
    billed = Shipment.query.filter(
        Shipment.rate > 0, Shipment.status != "cancelled").all()

    total_revenue = sum(s.rate for s in billed)
    avg_rate      = total_revenue / len(billed) if billed else 0

    by_customer, by_carrier = {}, {}
    for s in billed:
        n = names.get(s.customer_id, "Unknown")
        by_customer.setdefault(n, {"count": 0, "total": 0.0})
        by_customer[n]["count"] += 1
        by_customer[n]["total"] += s.rate
    for s in billed:
        if not s.carrier_id:
            continue
        n = names.get(s.carrier_id, s.carrier_id)
        by_carrier.setdefault(n, {"count": 0, "total": 0.0})
        by_carrier[n]["count"] += 1
        by_carrier[n]["total"] += s.rate

    out = io.StringIO()
    w   = csv.writer(out)
    w.writerow(["Freight Daddy CRM - Revenue Report"])
    w.writerow(["Total Shipments", len(billed)])
    w.writerow(["Total Revenue",   f"${total_revenue:,.2f}"])
    w.writerow(["Average Rate",    f"${avg_rate:,.2f}"])
    w.writerow([])
    w.writerow(["BY CUSTOMER", "", "", ""])
    w.writerow(["Customer", "Loads", "Total Revenue", "Avg Rate"])
    for name, d in sorted(by_customer.items(), key=lambda x: -x[1]["total"]):
        w.writerow([name, d["count"], f"${d['total']:,.2f}", f"${d['total']/d['count']:,.2f}"])
    w.writerow([])
    w.writerow(["BY CARRIER", "", "", ""])
    w.writerow(["Carrier", "Loads", "Total Revenue", "Avg Rate"])
    for name, d in sorted(by_carrier.items(), key=lambda x: -x[1]["total"]):
        w.writerow([name, d["count"], f"${d['total']:,.2f}", f"${d['total']/d['count']:,.2f}"])

    return Response(out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=revenue_report.csv"})


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = not getattr(sys, "frozen", False)
    print("Starting Freight Daddy CRM...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(host="0.0.0.0", port=port, debug=debug)
