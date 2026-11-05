"""Phase 1 foundation for satcom-erp (SPEC_PHASE1.md section 2). Idempotent.

Run (after satcom_demo_cleanup.run):
    bench --site frontend execute erpnext.satcom_p1_foundation.run
Each step compares before it writes and prints only what it changed, so a second run reports
"0 changes". Built so far: 2.1 settings, 2.2 roles and demo users, 2.3 warehouses, 2.4 item codes.
Copy erpnext/server_scripts and erpnext/client_scripts to /tmp/satcom_scripts in the backend
container first (the installer reads the script sources from there).
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"

_changes = []


def _log(msg):
    print(f"[p1-foundation] {msg}")


def _set_values(doctype, name, values):
    """Set fields on one record (name=None for a single doctype), saving only if something differs."""
    doc = frappe.get_single(doctype) if name is None else frappe.get_doc(doctype, name)
    diff = {f: v for f, v in values.items() if doc.get(f) != v}
    if not diff:
        return
    for field, value in diff.items():
        if not doc.meta.has_field(field):
            frappe.throw(f"{doctype} has no field {field} in this version")
        old, new = repr(doc.get(field)), repr(value)
        if len(old) + len(new) > 120:  # scripts etc.: say that it changed, not what
            old, new = f"<{len(str(doc.get(field) or ''))} chars>", f"<{len(str(value))} chars>"
        _changes.append(f"{doctype}{' ' + name if name else ''}: {field} {old} -> {new}")
        _log(_changes[-1])
        doc.set(field, value)
    doc.save()


# 2.1 Settings -------------------------------------------------------------------------------

def settings():
    # Perpetual inventory off, so stock never posts GL entries (accounts stay in Tally).
    _set_values("Company", COMPANY, {"enable_perpetual_inventory": 0})
    active_gl = frappe.db.count("GL Entry", {"is_cancelled": 0})
    if active_gl:
        frappe.throw(f"{active_gl} active GL entries exist; accounts must stay in Tally")
    # Valuation stays FIFO (OPEN, spec section 11): checked, never changed here.
    valuation = frappe.db.get_single_value("Stock Settings", "valuation_method")
    if valuation != "FIFO":
        frappe.throw(f"Stock Settings valuation method is {valuation}, spec keeps FIFO (open item)")
    _set_values("Buying Settings", None, {
        "supp_master_name": "Supplier Name",
        "po_required": "No",
        "pr_required": "No",
        "maintain_same_rate": 0,  # POs must allow the approved quotation's rate
    })


# 2.2 Roles ----------------------------------------------------------------------------------

CUSTOM_ROLES = ["Satcom Approver", "Satcom Indenter"]
# Satcom role (one Role Profile each; a user may hold several) -> ERPNext roles. Accounts: phase 3.
ROLE_PROFILES = {
    "Satcom Approver": ["Satcom Approver", "Purchase Manager", "Stock User"],
    "Satcom Indenter": ["Satcom Indenter", "Projects User", "Purchase User"],
    "Satcom Purchase": ["Purchase User"],
    "Satcom Stores": ["Stock User", "Item Manager"],
    "Satcom QC": ["Quality Manager", "Stock User"],
}
# Test users for the workflows (spec 2.2): no password, so they can't sign in until one is set.
DEMO_USERS = {
    "demo.approver1@example.com": ("Demo Approver 1", ["Satcom Approver"]),
    "demo.approver2@example.com": ("Demo Approver 2", ["Satcom Approver"]),
    "demo.indenter@example.com": ("Demo Indenter", ["Satcom Indenter", "Satcom Purchase"]),
    "demo.stores@example.com": ("Demo Stores", ["Satcom Stores", "Satcom QC"]),
    "demo.allroles@example.com": ("Demo All Roles", list(ROLE_PROFILES)),
}


def _change(msg):
    _changes.append(msg)
    _log(msg)


def roles():
    for name in CUSTOM_ROLES:
        if not frappe.db.exists("Role", name):
            frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1, "is_custom": 1}).insert()
            _change(f"role {name}")
        else:
            _set_values("Role", name, {"desk_access": 1, "disabled": 0})

    for profile, wanted in ROLE_PROFILES.items():
        if not frappe.db.exists("Role Profile", profile):
            frappe.get_doc({"doctype": "Role Profile", "role_profile": profile,
                            "roles": [{"role": r} for r in wanted]}).insert()
            _change(f"role profile {profile}: {', '.join(wanted)}")
            continue
        doc = frappe.get_doc("Role Profile", profile)
        have = sorted(r.role for r in doc.roles)
        if have != sorted(wanted):
            doc.set("roles", [{"role": r} for r in wanted])
            doc.save()  # Frappe pushes the new roles to every user holding the profile
            _change(f"role profile {profile}: {have} -> {sorted(wanted)}")

    for email, (full_name, profiles) in DEMO_USERS.items():
        if not frappe.db.exists("User", email):
            first, _, last = full_name.partition(" ")
            frappe.get_doc({
                "doctype": "User", "email": email, "first_name": first, "last_name": last,
                "user_type": "System User", "enabled": 1, "send_welcome_email": 0,
                "role_profiles": [{"role_profile": p} for p in profiles],
            }).insert()
            _change(f"user {email}: {', '.join(profiles)}")
            continue
        user = frappe.get_doc("User", email)
        have = sorted(p.role_profile for p in user.role_profiles)
        if have != sorted(profiles) or not user.enabled:
            user.enabled = 1
            user.set("role_profiles", [{"role_profile": p} for p in profiles])
            user.save()
            _change(f"user {email}: {have} -> {sorted(profiles)}")


# 2.3 Warehouses -----------------------------------------------------------------------------

ABBR = "STPL"
ROOT_WAREHOUSE = f"All Warehouses - {ABBR}"
# new warehouse -> extra fields. Rejected is flagged so Pick Lists never pick rejected stock.
NEW_WAREHOUSES = {
    "Rejected": {"is_rejected_warehouse": 1},
    "Repair RMA": {},
}
DISABLE_IF_EMPTY = ["Raw Material"]


def warehouses():
    for name, extra in NEW_WAREHOUSES.items():
        full = f"{name} - {ABBR}"
        if not frappe.db.exists("Warehouse", full):
            frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "company": COMPANY,
                            "parent_warehouse": ROOT_WAREHOUSE, "is_group": 0, **extra}).insert()
            _change(f"warehouse {full}")
        else:
            _set_values("Warehouse", full, {"disabled": 0, **extra})

    for name in DISABLE_IF_EMPTY:
        full = f"{name} - {ABBR}"
        if not frappe.db.exists("Warehouse", full) or frappe.db.get_value("Warehouse", full, "disabled"):
            continue
        used = (frappe.db.count("Stock Ledger Entry", {"warehouse": full})
                + frappe.db.count("Bin", {"warehouse": full})
                + frappe.db.count("Item Default", {"default_warehouse": full})
                + frappe.db.count("Warehouse", {"parent_warehouse": full}))
        if used:
            frappe.throw(f"{full} is not empty or still referenced ({used} rows); not disabling")
        _set_values("Warehouse", full, {"disabled": 1})


# Shared helpers for custom fields and scripts (used from 2.4 on) -----------------------------

# Script sources are copied next to the module run (see README): <SCRIPTS_DIR>/server_scripts, client_scripts
SCRIPTS_DIR = "/tmp/satcom_scripts"


def _custom_field(dt, fieldname, **props):
    """Create or update one Custom Field; props are compared field by field."""
    name = frappe.db.get_value("Custom Field", {"dt": dt, "fieldname": fieldname})
    if not name:
        frappe.get_doc({"doctype": "Custom Field", "dt": dt, "fieldname": fieldname, **props}).insert()
        _change(f"custom field {dt}.{fieldname}")
        return
    doc = frappe.get_doc("Custom Field", name)
    diff = {k: v for k, v in props.items() if (doc.get(k) or None) != (v or None)}
    if diff:
        doc.update(diff)
        doc.save()
        _change(f"custom field {dt}.{fieldname}: {sorted(diff)}")


def _source(kind, filename):
    with open(f"{SCRIPTS_DIR}/{kind}/{filename}", encoding="utf-8") as f:
        return f.read()


def _server_script(name, doctype, event, filename):
    values = {"script_type": "DocType Event", "reference_doctype": doctype, "doctype_event": event,
              "script": _source("server_scripts", filename), "disabled": 0}
    if not frappe.db.exists("Server Script", name):
        frappe.get_doc({"doctype": "Server Script", "name": name, **values}).insert()
        _change(f"server script {name}")
    else:
        _set_values("Server Script", name, values)


def _client_script(name, dt, filename):
    values = {"dt": dt, "view": "Form", "enabled": 1, "script": _source("client_scripts", filename)}
    if not frappe.db.exists("Client Script", name):
        frappe.get_doc({"doctype": "Client Script", "name": name, **values}).insert()
        _change(f"client script {name}")
    else:
        _set_values("Client Script", name, values)


def _doctype_property(doctype, prop, value, property_type):
    current = frappe.db.get_value("Property Setter", {"doc_type": doctype, "doctype_or_field": "DocType",
                                                       "property": prop}, "value")
    if current is not None and str(current) == str(value):
        return
    frappe.make_property_setter({"doctype": doctype, "doctype_or_field": "DocType", "property": prop,
                                 "value": value, "property_type": property_type}, validate_fields_for_doctype=False)
    _change(f"{doctype} property {prop} = {value}")


def _field_property(doctype, fieldname, prop, value, property_type):
    current = frappe.db.get_value("Property Setter", {"doc_type": doctype, "doctype_or_field": "DocField",
                                                       "field_name": fieldname, "property": prop}, "value")
    if current is not None and str(current) == str(value):
        return
    frappe.make_property_setter({"doctype": doctype, "doctype_or_field": "DocField", "fieldname": fieldname,
                                 "property": prop, "value": value, "property_type": property_type},
                                validate_fields_for_doctype=False)
    _change(f"{doctype}.{fieldname} {prop} = {value}")


# 2.4 Item code scheme -----------------------------------------------------------------------

# Item Group -> (prefix, code type); groups without an entry keep no prefix and get no new items
ITEM_GROUPS = {
    "Resistors": ("RES", "Specs"),
    "Capacitors": ("CAP", "Specs"),
    "Inductors": ("IND", "Specs"),
    "Fasteners and Hardware": ("HWR", "Specs"),
    "ICs and Semiconductors": ("ICS", "Number"),
    "RF Components": ("RFC", "Number"),
    "Connectors": ("CON", "Number"),
    "Cables and Wire": ("CBL", "Number"),
    "Bare PCBs": ("PCB", "Number"),
    "Fabricated and Machined Parts": ("MEC", "Number"),
    "Enclosures and Racks": ("ENC", "Number"),
    "Consumable": ("CNS", "Number"),
    "Packaging": ("PKG", "Number"),
    "Tools & Spares": ("TOL", "Number"),
    "Sub Assemblies": ("SAS", "Number"),
    "Finished Goods": ("FGD", "Number"),
}
# Attribute -> seed values (value = abbreviation, so variant codes read RES-10K-0603). Stores adds more.
ATTRIBUTES = {
    "Resistance": ["10K", "4K7", "100R"],
    "Package": ["0402", "0603", "0805", "1206", "THT"],
    "Capacitance": ["100N", "10U", "22P"],
    "Voltage": ["16V", "50V"],
    "Inductance": ["10U", "1U", "100N"],
    "Thread Size": ["M3X10", "M3X6", "M4X10"],
    "Material": ["SS", "MS", "ZN"],
}
# Specs templates: code = prefix; attribute order = order in the variant code. Bought in lots -> batch.
TEMPLATES = {
    "RES": ("Resistor", "Resistors", ["Resistance", "Package"]),
    "CAP": ("Capacitor", "Capacitors", ["Capacitance", "Package", "Voltage"]),
    "IND": ("Inductor", "Inductors", ["Inductance", "Package"]),
    "HWR": ("Fastener", "Fasteners and Hardware", ["Thread Size", "Material"]),
}
# a variant needs its own series, built from its own code by the rules script
VARIANT_FIELDS_NOT_COPIED = ["serial_no_series", "batch_number_series"]
# copied, so a variant's description = template's ("Resistor") + its attribute values
VARIANT_FIELDS_COPIED = ["description"]


def items():
    _custom_field("Item Group", "satcom_prefix", label="Code Prefix", fieldtype="Data",
                  insert_after="parent_item_group", length=3, in_list_view=1,
                  description="3 letters at the start of every item code in this group")
    _custom_field("Item Group", "satcom_code_type", label="Code Type", fieldtype="Select",
                  options="\nSpecs\nNumber", insert_after="satcom_prefix",
                  description="Specs: variants of one template (RES-10K-0603). Number: running number (RFC-0102).")

    for group, (prefix, code_type) in ITEM_GROUPS.items():
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc({"doctype": "Item Group", "item_group_name": group,
                            "parent_item_group": "All Item Groups", "is_group": 0,
                            "satcom_prefix": prefix, "satcom_code_type": code_type}).insert()
            _change(f"item group {group} ({prefix}, {code_type})")
        else:
            _set_values("Item Group", group, {"satcom_prefix": prefix, "satcom_code_type": code_type})

    _custom_field("Item", "satcom_part_section", label="Part Identification", fieldtype="Section Break",
                  insert_after="is_customer_provided_item")  # Details tab, after Item Attributes
    _custom_field("Item", "satcom_mpn", label="Manufacturer Part No", fieldtype="Data",
                  insert_after="satcom_part_section", in_standard_filter=1, search_index=1)
    _custom_field("Item", "satcom_manufacturer", label="Manufacturer", fieldtype="Data",
                  insert_after="satcom_mpn")
    _custom_field("Item", "satcom_part_cb", fieldtype="Column Break", insert_after="satcom_manufacturer")
    _custom_field("Item", "satcom_drawing_no", label="Drawing No", fieldtype="Data",
                  insert_after="satcom_part_cb", in_standard_filter=1)
    _custom_field("Item", "satcom_drawing_rev", label="Drawing Rev", fieldtype="Data",
                  insert_after="satcom_drawing_no")

    for attribute, values in ATTRIBUTES.items():
        if not frappe.db.exists("Item Attribute", attribute):
            frappe.get_doc({"doctype": "Item Attribute", "attribute_name": attribute,
                            "item_attribute_values": [{"attribute_value": v, "abbr": v} for v in values]}).insert()
            _change(f"item attribute {attribute}: {', '.join(values)}")
            continue
        doc = frappe.get_doc("Item Attribute", attribute)
        have = {v.attribute_value for v in doc.item_attribute_values}
        missing = [v for v in values if v not in have]  # only add: stores' own values are kept
        if missing:
            for v in missing:
                doc.append("item_attribute_values", {"attribute_value": v, "abbr": v})
            doc.save()
            _change(f"item attribute {attribute}: added {', '.join(missing)}")

    ivs = frappe.get_single("Item Variant Settings")
    have = [f.field_name for f in ivs.fields]
    wanted = [f for f in have if f not in VARIANT_FIELDS_NOT_COPIED]
    wanted += [f for f in VARIANT_FIELDS_COPIED if f not in wanted]
    if wanted != have:
        ivs.set("fields", [{"field_name": f} for f in wanted])
        ivs.save()
        _change(f"Item Variant Settings: copy {', '.join(VARIANT_FIELDS_COPIED)}, "
                f"not {', '.join(VARIANT_FIELDS_NOT_COPIED)}")

    # the full form (custom fields, client script) instead of the quick-entry dialog
    _doctype_property("Item", "quick_entry", 0, "Check")
    # sections holding required inputs stay open (they were collapsed on a new item)
    for section in ("section_break_11", "serial_nos_and_batches"):  # Description; Serial Nos / Batches
        _field_property("Item", section, "collapsible", 0, "Check")

    _server_script("Satcom Item - number", "Item", "Before Insert", "satcom_item_number.py")
    _server_script("Satcom Item - rules", "Item", "Before Save", "satcom_item_rules.py")
    _client_script("Satcom Item", "Item", "satcom_item.js")

    for code, (item_name, group, attributes) in TEMPLATES.items():
        if frappe.db.exists("Item", code):
            _set_values("Item", code, {"description": item_name})
            continue
        frappe.get_doc({
            "doctype": "Item", "item_code": code, "item_name": item_name, "item_group": group,
            "stock_uom": "Nos", "is_stock_item": 1, "has_variants": 1, "variant_based_on": "Item Attribute",
            "attributes": [{"attribute": a} for a in attributes],
            "has_batch_no": 1, "create_new_batch": 1,
            "description": item_name,
        }).insert()
        _change(f"template item {code} ({', '.join(attributes)})")


def run():
    _changes.clear()
    settings()
    roles()
    warehouses()
    items()
    frappe.db.commit()
    frappe.clear_cache()
    _log(f"done: {len(_changes)} changes")
