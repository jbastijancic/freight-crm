import json
import sys
from pathlib import Path

CONTACTS_FILE = Path(__file__).parent / "contacts.json"
CONFIG_FILE   = Path(__file__).parent / "config.json"


def load_contacts():
    with open(CONTACTS_FILE) as f:
        return json.load(f)["contacts"]


def save_contacts(contacts):
    with open(CONTACTS_FILE, "w") as f:
        json.dump({"contacts": contacts}, f, indent=2)


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def next_id(contacts):
    config = load_config()
    prefix = config["id_prefixes"]["contact"]
    nums = [int(c["id"].replace(prefix, "")) for c in contacts if c["id"].startswith(prefix)]
    return f"{prefix}{(max(nums) + 1) if nums else 1:03d}"


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
        print(f"  {key:<15} {value}")
    print()


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

    company  = input("Company (optional): ").strip()
    phone    = input("Phone (optional): ").strip()
    email    = input("Email (optional): ").strip()
    address  = input("Address (optional): ").strip()
    notes    = input("Notes (optional): ").strip()

    from datetime import date
    new_contact = {
        "id":         next_id(contacts),
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


COMMANDS = {
    "list":   (cmd_list,   "List all contacts. Filter by type: python crm.py list carrier"),
    "search": (cmd_search, "Search by name, company, or email: python crm.py search <query>"),
    "show":   (cmd_show,   "Show full details for a contact: python crm.py show <id>"),
    "add":    (cmd_add,    "Add a new contact interactively: python crm.py add"),
}


def print_help():
    config = load_config()
    print(f"\n{config['company']['name']} CRM\n")
    print("Commands:")
    for name, (_, description) in COMMANDS.items():
        print(f"  {name:<10} {description}")
    print()


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print_help()
    else:
        command, remaining_args = sys.argv[1], sys.argv[2:]
        COMMANDS[command][0](remaining_args)
