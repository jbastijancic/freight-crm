import json
import sys
from datetime import date
from pathlib import Path

CONTACTS_FILE  = Path(__file__).parent / "contacts.json"
SHIPMENTS_FILE = Path(__file__).parent / "shipments.json"
CONFIG_FILE    = Path(__file__).parent / "config.json"


# ── Loaders / savers ─────────────────────────────────────────────────────────

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


# ── ID helpers ────────────────────────────────────────────────────────────────

def next_contact_id(contacts):
    prefix = load_config()["id_prefixes"]["contact"]
    nums = [int(c["id"].replace(prefix, "")) for c in contacts if c["id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"

def next_shipment_id(shipments):
    prefix = load_config()["id_prefixes"]["shipment"]
    nums = [int(s["id"].replace(prefix, "")) for s in shipments if s["id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"


# ── Contact commands ──────────────────────────────────────────────────────────

def cmd_list(args):
    contacts = load_contacts()
    type_filter = args[0] if args else None
    if type_filter:
        contacts = [c for c in contacts if c["type"] == type_filter]
    if not contacts:
        print("No contacts found.")
        return
    print(f"\n{'ID':<8} {'TYPE':<10} {'NAME':<25} {'COMPANY':<25} {'PHONE'}")
    print("-" * 85)
    for c in contacts:
        print(f"{c['id']:<8} {c['type']:<10} {c['name']:<25} {c.get('company',''):<25} {c.get('phone','')}")
    print()

def cmd_search(args):
    if not args:
        print("Usage: python crm.py search <query>")
        return
    query = " ".join(args).lower()
    contacts = load_contacts()
    results = [
        c for c in contacts
        if query in c.get("name", "").lower()
        or query in c.get("company", "").lower()
        or query in c.get("email", "").lower()
    ]
    if not results:
        print(f"No contacts matching '{query}'.")
        return
    print(f"\nResults for '{query}':")
    print(f"\n{'ID':<8} {'TYPE':<10} {'NAME':<25} {'COMPANY':<25} {'PHONE'}")
    print("-" * 85)
    for c in results:
        print(f"{c['id']:<8} {c['type']:<10} {c['name']:<25} {c.get('company',''):<25} {c.get('phone','')}")
    print()

def cmd_show(args):
    if not args:
        print("Usage: python crm.py show <id>")
        return
    contact_id = args[0].upper()
    contacts = load_contacts()
    match = next((c for c in contacts if c["id"].upper() == contact_id), None)
    if not match:
        print(f"No contact with ID '{contact_id}'.")
        return
    print()
    for key, value in match.items():
        if key == "notes":
            print(f"  {'notes':<15}")
            if value:
                for entry in value:
                    print(f"    [{entry['date']}] {entry['text']}")
            else:
                print(f"    (none)")
        else:
            print(f"  {key:<15} {value}")
    print()

def cmd_edit(args):
    if not args:
        print("Usage: python crm.py edit <id>")
        return

    contact_id = args[0].upper()
    contacts = load_contacts()
    match = next((c for c in contacts if c["id"].upper() == contact_id), None)

    if not match:
        print(f"No contact with ID '{contact_id}'.")
        return

    config = load_config()
    valid_types = config["contact_types"]
    editable = ["type", "name", "company", "phone", "email", "address", "active"]

    print(f"\nEditing {contact_id} - {match['name']}")
    print("Press Enter to keep the current value.\n")

    for field in editable:
        current = match.get(field, "")
        new_val = input(f"  {field} [{current}]: ").strip()
        if new_val == "":
            continue
        if field == "type" and new_val.lower() not in valid_types:
            print(f"    Invalid type, keeping '{current}'.")
            continue
        if field == "active":
            match[field] = new_val.lower() in ("true", "yes", "1")
        else:
            match[field] = new_val

    # Notes are appended as a new timestamped entry, never overwritten
    existing_notes = match.get("notes", [])
    if existing_notes:
        print(f"\n  Existing notes:")
        for entry in existing_notes:
            print(f"    [{entry['date']}] {entry['text']}")
    new_note = input("\n  Add a new note (Enter to skip): ").strip()
    if new_note:
        match["notes"] = existing_notes + [{"date": date.today().isoformat(), "text": new_note}]

    save_contacts(contacts)
    print(f"\nSaved changes to {contact_id} - {match['name']}\n")


def cmd_add(args):
    contacts = load_contacts()
    config = load_config()
    valid_types = config["contact_types"]
    print("\nAdd a new contact (press Enter to skip optional fields)\n")
    contact_type = input(f"Type ({'/'.join(valid_types)}): ").strip().lower()
    if contact_type not in valid_types:
        print(f"Invalid type. Choose from: {', '.join(valid_types)}")
        return
    name = input("Name: ").strip()
    if not name:
        print("Name is required.")
        return
    company   = input("Company (optional): ").strip()
    phone     = input("Phone (optional): ").strip()
    email     = input("Email (optional): ").strip()
    address   = input("Address (optional): ").strip()
    note_text = input("Notes (optional): ").strip()
    notes = [{"date": date.today().isoformat(), "text": note_text}] if note_text else []
    new_contact = {
        "id":         next_contact_id(contacts),
        "type":       contact_type,
        "name":       name,
        "company":    company,
        "phone":      phone,
        "email":      email,
        "address":    address,
        "notes":      notes,
        "created_at": date.today().isoformat(),
        "active":     True
    }
    contacts.append(new_contact)
    save_contacts(contacts)
    print(f"\nAdded {new_contact['id']} — {name}\n")


# ── Shipment commands ─────────────────────────────────────────────────────────

def cmd_shipments(args):
    sub = args[0] if args else None
    sub_args = args[1:]

    if sub == "list":
        _shipments_list(sub_args)
    elif sub == "show":
        _shipments_show(sub_args)
    elif sub == "add":
        _shipments_add()
    elif sub == "status":
        _shipments_status(sub_args)
    else:
        print("\nShipment commands:")
        print("  python crm.py shipments list               List all shipments")
        print("  python crm.py shipments list <status>      Filter by status")
        print("  python crm.py shipments show <id>          Show full shipment details")
        print("  python crm.py shipments add                Log a new shipment")
        print("  python crm.py shipments status <id> <new>  Update shipment status")
        print()

def _shipments_list(args):
    shipments = load_shipments()
    contacts  = load_contacts()
    status_filter = args[0] if args else None

    if status_filter:
        shipments = [s for s in shipments if s["status"] == status_filter]

    if not shipments:
        print("No shipments found.")
        return

    # Build a quick id→name lookup
    names = {c["id"]: c["name"] for c in contacts}

    print(f"\n{'ID':<8} {'STATUS':<12} {'CUSTOMER':<22} {'CARRIER':<22} {'ORIGIN':<18} {'DESTINATION':<18} {'RATE'}")
    print("-" * 110)
    for s in shipments:
        customer = names.get(s.get("customer_id", ""), s.get("customer_id", ""))
        carrier  = names.get(s.get("carrier_id", ""),  s.get("carrier_id", ""))
        rate     = f"${s.get('rate', 0):,.2f}"
        print(f"{s['id']:<8} {s['status']:<12} {customer:<22} {carrier:<22} {s.get('origin',''):<18} {s.get('destination',''):<18} {rate}")
    print()

def _shipments_show(args):
    if not args:
        print("Usage: python crm.py shipments show <id>")
        return
    shipment_id = args[0].upper()
    shipments = load_shipments()
    contacts  = load_contacts()
    match = next((s for s in shipments if s["id"].upper() == shipment_id), None)
    if not match:
        print(f"No shipment with ID '{shipment_id}'.")
        return
    names = {c["id"]: f"{c['name']} ({c['id']})" for c in contacts}
    print()
    for key, value in match.items():
        if key in ("customer_id", "carrier_id"):
            value = names.get(value, value)
        if key == "rate":
            value = f"${value:,.2f}"
        print(f"  {key:<15} {value}")
    print()

def _shipments_add():
    shipments = load_shipments()
    contacts  = load_contacts()
    config    = load_config()
    valid_statuses = config["shipment_statuses"]

    print("\nLog a new shipment (press Enter to skip optional fields)\n")

    # Show contacts for reference
    print("  Contacts on file:")
    for c in contacts:
        print(f"    {c['id']}  {c['name']} ({c['type']})")
    print()

    customer_id = input("Customer ID: ").strip().upper()
    carrier_id  = input("Carrier ID (optional): ").strip().upper()
    origin      = input("Origin city, state: ").strip()
    destination = input("Destination city, state: ").strip()
    pickup_date = input("Pickup date (YYYY-MM-DD): ").strip()
    delivery_date = input("Delivery date (YYYY-MM-DD, optional): ").strip()
    rate        = input("Rate in USD (optional): ").strip()
    commodity   = input("Commodity (optional): ").strip()
    weight      = input("Weight in lbs (optional): ").strip()
    status      = input(f"Status ({'/'.join(valid_statuses)}) [default: booked]: ").strip().lower() or "booked"
    notes       = input("Notes (optional): ").strip()

    if status not in valid_statuses:
        print(f"Invalid status. Choose from: {', '.join(valid_statuses)}")
        return

    new_shipment = {
        "id":            next_shipment_id(shipments),
        "status":        status,
        "customer_id":   customer_id,
        "carrier_id":    carrier_id or "",
        "origin":        origin,
        "destination":   destination,
        "pickup_date":   pickup_date,
        "delivery_date": delivery_date,
        "rate":          float(rate) if rate else 0.0,
        "commodity":     commodity,
        "weight_lbs":    int(weight) if weight else 0,
        "notes":         notes
    }

    shipments.append(new_shipment)
    save_shipments(shipments)
    print(f"\nLogged {new_shipment['id']} — {origin} → {destination}\n")

def _shipments_status(args):
    if len(args) < 2:
        print("Usage: python crm.py shipments status <id> <new_status>")
        return
    shipment_id = args[0].upper()
    new_status  = args[1].lower()
    config      = load_config()
    valid_statuses = config["shipment_statuses"]

    if new_status not in valid_statuses:
        print(f"Invalid status '{new_status}'. Choose from: {', '.join(valid_statuses)}")
        return

    shipments = load_shipments()
    match = next((s for s in shipments if s["id"].upper() == shipment_id), None)
    if not match:
        print(f"No shipment with ID '{shipment_id}'.")
        return

    old_status = match["status"]
    match["status"] = new_status
    save_shipments(shipments)
    print(f"\n{shipment_id} updated: {old_status} -> {new_status}\n")


# ── Revenue report ───────────────────────────────────────────────────────────

def cmd_report(args):
    shipments = load_shipments()
    contacts  = load_contacts()
    names     = {c["id"]: c["name"] for c in contacts}

    # Only count shipments that have a rate
    billed = [s for s in shipments if s.get("rate", 0) > 0]

    if not billed:
        print("\nNo shipments with rates found.\n")
        return

    total_revenue   = sum(s["rate"] for s in billed)
    total_shipments = len(billed)
    avg_rate        = total_revenue / total_shipments

    # Revenue by customer
    by_customer = {}
    for s in billed:
        cid = s.get("customer_id", "Unknown")
        name = names.get(cid, cid)
        if name not in by_customer:
            by_customer[name] = {"count": 0, "total": 0.0}
        by_customer[name]["count"] += 1
        by_customer[name]["total"] += s["rate"]

    # Revenue by carrier
    by_carrier = {}
    for s in billed:
        cid = s.get("carrier_id", "")
        if not cid:
            continue
        name = names.get(cid, cid)
        if name not in by_carrier:
            by_carrier[name] = {"count": 0, "total": 0.0}
        by_carrier[name]["count"] += 1
        by_carrier[name]["total"] += s["rate"]

    # ── Print report ──────────────────────────────────────────────────────────
    config = load_config()
    print(f"\n{'=' * 55}")
    print(f"  {config['company']['name']} - Revenue Report")
    print(f"{'=' * 55}")
    print(f"  Total shipments : {total_shipments}")
    print(f"  Total revenue   : ${total_revenue:,.2f}")
    print(f"  Average rate    : ${avg_rate:,.2f}")

    print(f"\n  {'BY CUSTOMER'}")
    print(f"  {'-' * 50}")
    print(f"  {'Name':<25} {'Loads':>6}  {'Revenue':>12}  {'Avg Rate':>10}")
    print(f"  {'-' * 50}")
    for name, data in sorted(by_customer.items(), key=lambda x: -x[1]["total"]):
        avg = data["total"] / data["count"]
        print(f"  {name:<25} {data['count']:>6}  ${data['total']:>11,.2f}  ${avg:>9,.2f}")

    if by_carrier:
        print(f"\n  {'BY CARRIER'}")
        print(f"  {'-' * 50}")
        print(f"  {'Name':<25} {'Loads':>6}  {'Revenue':>12}  {'Avg Rate':>10}")
        print(f"  {'-' * 50}")
        for name, data in sorted(by_carrier.items(), key=lambda x: -x[1]["total"]):
            avg = data["total"] / data["count"]
            print(f"  {name:<25} {data['count']:>6}  ${data['total']:>11,.2f}  ${avg:>9,.2f}")

    print(f"\n{'=' * 55}\n")


# ── Command registry & help ───────────────────────────────────────────────────

COMMANDS = {
    "list":      (cmd_list,      "List contacts. Filter by type: python crm.py list carrier"),
    "search":    (cmd_search,    "Search contacts: python crm.py search <query>"),
    "show":      (cmd_show,      "Show contact details: python crm.py show <id>"),
    "add":       (cmd_add,       "Add a new contact interactively"),
    "edit":      (cmd_edit,      "Edit an existing contact: python crm.py edit <id>"),
    "shipments": (cmd_shipments, "Manage shipments: python crm.py shipments <list|show|add|status>"),
    "report":    (cmd_report,    "Revenue summary by customer and carrier"),
}

def print_help():
    config = load_config()
    print(f"\n{config['company']['name']} CRM\n")
    print("Commands:")
    for name, (_, description) in COMMANDS.items():
        print(f"  {name:<12} {description}")
    print()

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print_help()
    else:
        command, remaining_args = sys.argv[1], sys.argv[2:]
        COMMANDS[command][0](remaining_args)
