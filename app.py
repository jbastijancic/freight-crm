from flask import Flask, render_template, request, redirect, url_for
import json
import os
import sys
from pathlib import Path
from datetime import date

# ── Path resolution (dev vs PyInstaller bundle vs cloud) ─────────────────────
# Templates/static live inside the bundle when frozen; alongside app.py in dev.
# Data files (JSON) always live next to the executable so they stay writable.

if getattr(sys, "frozen", False):
    _RESOURCE_DIR = Path(sys._MEIPASS)          # bundled assets (read-only)
    _DATA_DIR     = Path(sys.executable).parent  # writable folder next to .exe
else:
    _RESOURCE_DIR = Path(__file__).parent
    _DATA_DIR     = Path(__file__).parent

app = Flask(__name__,
    template_folder=str(_RESOURCE_DIR / "templates"),
    static_folder=str(_RESOURCE_DIR / "static"),
)

CONTACTS_FILE  = _DATA_DIR / "contacts.json"
SHIPMENTS_FILE = _DATA_DIR / "shipments.json"
CONFIG_FILE    = _DATA_DIR / "config.json"


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_contacts():
    with open(CONTACTS_FILE) as f:
        return json.load(f)["contacts"]

def save_contacts(contacts):
    with open(CONTACTS_FILE, "w") as f:
        json.dump({"contacts": contacts}, f, indent=2)

def load_shipments():
    with open(SHIPMENTS_FILE) as f:
        return json.load(f)["shipments"]

def save_shipments(shipments):
    with open(SHIPMENTS_FILE, "w") as f:
        json.dump({"shipments": shipments}, f, indent=2)

def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

def next_contact_id(contacts):
    prefix = load_config()["id_prefixes"]["contact"]
    nums = [int(c["id"].replace(prefix, "")) for c in contacts if c["id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"

def next_shipment_id(shipments):
    prefix = load_config()["id_prefixes"]["shipment"]
    nums = [int(s["id"].replace(prefix, "")) for s in shipments if s["id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    contacts  = load_contacts()
    shipments = load_shipments()
    config    = load_config()
    names     = {c["id"]: c["name"] for c in contacts}

    in_transit   = [s for s in shipments if s["status"] == "in_transit"]
    total_revenue = sum(s.get("rate", 0) for s in shipments if s["status"] != "cancelled")
    recent       = sorted(shipments, key=lambda s: s.get("pickup_date", ""), reverse=True)[:5]

    return render_template("dashboard.html",
        config=config,
        total_contacts=len(contacts),
        total_shipments=len(shipments),
        in_transit=len(in_transit),
        total_revenue=total_revenue,
        recent=recent,
        names=names,
    )


# ── Contacts ──────────────────────────────────────────────────────────────────

@app.route("/contacts")
def contacts_list():
    all_contacts = load_contacts()
    config       = load_config()
    q            = request.args.get("q", "").lower()
    type_filter  = request.args.get("type", "")

    filtered = all_contacts
    if type_filter:
        filtered = [c for c in filtered if c["type"] == type_filter]
    if q:
        filtered = [c for c in filtered if
            q in c.get("name", "").lower() or
            q in c.get("company", "").lower() or
            q in c.get("email", "").lower()
        ]

    return render_template("contacts.html",
        contacts=filtered, config=config, q=q, type_filter=type_filter)


@app.route("/contacts/new", methods=["GET", "POST"])
def contact_new():
    config = load_config()
    if request.method == "POST":
        contacts  = load_contacts()
        note_text = request.form.get("note", "").strip()
        new_contact = {
            "id":         next_contact_id(contacts),
            "type":       request.form["type"],
            "name":       request.form["name"],
            "company":    request.form.get("company", ""),
            "phone":      request.form.get("phone", ""),
            "email":      request.form.get("email", ""),
            "address":    request.form.get("address", ""),
            "notes":      [{"date": date.today().isoformat(), "text": note_text}] if note_text else [],
            "created_at": date.today().isoformat(),
            "active":     True,
        }
        contacts.append(new_contact)
        save_contacts(contacts)
        return redirect(url_for("contact_detail", contact_id=new_contact["id"]))
    return render_template("contact_form.html", config=config, contact=None)


@app.route("/contacts/<contact_id>")
def contact_detail(contact_id):
    contacts = load_contacts()
    contact  = next((c for c in contacts if c["id"] == contact_id), None)
    if not contact:
        return "Contact not found", 404
    shipments = load_shipments()
    names     = {c["id"]: c["name"] for c in contacts}
    related   = [s for s in shipments
                 if s.get("customer_id") == contact_id or s.get("carrier_id") == contact_id]
    return render_template("contact_detail.html",
        contact=contact, related=related, names=names, config=load_config())


@app.route("/contacts/<contact_id>/edit", methods=["GET", "POST"])
def contact_edit(contact_id):
    contacts = load_contacts()
    contact  = next((c for c in contacts if c["id"] == contact_id), None)
    config   = load_config()
    if not contact:
        return "Contact not found", 404

    if request.method == "POST":
        contact["type"]    = request.form.get("type", contact["type"])
        contact["name"]    = request.form.get("name", contact["name"])
        contact["company"] = request.form.get("company", "")
        contact["phone"]   = request.form.get("phone", "")
        contact["email"]   = request.form.get("email", "")
        contact["address"] = request.form.get("address", "")
        contact["active"]  = request.form.get("active") == "on"
        new_note = request.form.get("new_note", "").strip()
        if new_note:
            contact.setdefault("notes", []).append(
                {"date": date.today().isoformat(), "text": new_note}
            )
        save_contacts(contacts)
        return redirect(url_for("contact_detail", contact_id=contact_id))

    return render_template("contact_form.html", config=config, contact=contact)


# ── Shipments ─────────────────────────────────────────────────────────────────

@app.route("/shipments")
def shipments_list():
    all_shipments = load_shipments()
    contacts      = load_contacts()
    config        = load_config()
    status_filter = request.args.get("status", "")

    filtered = all_shipments
    if status_filter:
        filtered = [s for s in filtered if s["status"] == status_filter]
    filtered = sorted(filtered, key=lambda s: s.get("pickup_date", ""), reverse=True)
    names = {c["id"]: c["name"] for c in contacts}

    return render_template("shipments.html",
        shipments=filtered, names=names, config=config, status_filter=status_filter)


@app.route("/shipments/new", methods=["GET", "POST"])
def shipment_new():
    contacts = load_contacts()
    config   = load_config()
    if request.method == "POST":
        shipments  = load_shipments()
        rate_str   = request.form.get("rate", "")
        weight_str = request.form.get("weight_lbs", "")
        new_shipment = {
            "id":            next_shipment_id(shipments),
            "status":        request.form.get("status", "booked"),
            "customer_id":   request.form.get("customer_id", ""),
            "carrier_id":    request.form.get("carrier_id", ""),
            "origin":        request.form.get("origin", ""),
            "destination":   request.form.get("destination", ""),
            "pickup_date":   request.form.get("pickup_date", ""),
            "delivery_date": request.form.get("delivery_date", ""),
            "rate":          float(rate_str) if rate_str else 0.0,
            "commodity":     request.form.get("commodity", ""),
            "weight_lbs":    int(weight_str) if weight_str else 0,
            "notes":         request.form.get("notes", ""),
        }
        shipments.append(new_shipment)
        save_shipments(shipments)
        return redirect(url_for("shipment_detail", shipment_id=new_shipment["id"]))
    return render_template("shipment_form.html", contacts=contacts, config=config)


@app.route("/shipments/<shipment_id>")
def shipment_detail(shipment_id):
    shipments = load_shipments()
    shipment  = next((s for s in shipments if s["id"] == shipment_id), None)
    if not shipment:
        return "Shipment not found", 404
    contacts = load_contacts()
    names    = {c["id"]: c["name"] for c in contacts}
    return render_template("shipment_detail.html",
        shipment=shipment, names=names, config=load_config())


@app.route("/shipments/<shipment_id>/status", methods=["POST"])
def shipment_status(shipment_id):
    shipments = load_shipments()
    shipment  = next((s for s in shipments if s["id"] == shipment_id), None)
    if shipment:
        shipment["status"] = request.form["status"]
        save_shipments(shipments)
    return redirect(url_for("shipment_detail", shipment_id=shipment_id))


# ── Report ────────────────────────────────────────────────────────────────────

@app.route("/report")
def report():
    shipments = load_shipments()
    contacts  = load_contacts()
    config    = load_config()
    names     = {c["id"]: c["name"] for c in contacts}
    billed    = [s for s in shipments if s.get("rate", 0) > 0 and s["status"] != "cancelled"]

    total_revenue = sum(s["rate"] for s in billed)
    avg_rate      = total_revenue / len(billed) if billed else 0

    by_customer = {}
    for s in billed:
        name = names.get(s.get("customer_id", ""), "Unknown")
        by_customer.setdefault(name, {"count": 0, "total": 0.0})
        by_customer[name]["count"] += 1
        by_customer[name]["total"] += s["rate"]

    by_carrier = {}
    for s in billed:
        cid = s.get("carrier_id", "")
        if not cid:
            continue
        name = names.get(cid, cid)
        by_carrier.setdefault(name, {"count": 0, "total": 0.0})
        by_carrier[name]["count"] += 1
        by_carrier[name]["total"] += s["rate"]

    by_customer = dict(sorted(by_customer.items(), key=lambda x: -x[1]["total"]))
    by_carrier  = dict(sorted(by_carrier.items(),  key=lambda x: -x[1]["total"]))

    return render_template("report.html",
        config=config, billed=billed, by_customer=by_customer,
        by_carrier=by_carrier, total_revenue=total_revenue,
        avg_rate=avg_rate, total_shipments=len(billed))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = not getattr(sys, "frozen", False)
    print("Starting Freight Daddy CRM...")
    print(f"Open http://localhost:{port} in your browser")
    app.run(host="0.0.0.0", port=port, debug=debug)
