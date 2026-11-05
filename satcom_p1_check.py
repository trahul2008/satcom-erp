"""Phase 1 acceptance check for satcom-erp (SPEC_PHASE1.md section 10). Read-only.

    bench --site frontend execute erpnext.satcom_p1_check.verify
Prints PASS/FAIL per line and a summary. It grows with each section as it is built; the DEMO
scenario (create_demo / cleanup, spec section 10) is added once the sections it needs exist.
Built so far: 1 demo cleanup, 2.1 settings, 2.2 roles, 2.3 warehouses, 2.4 item codes.
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"

_results = []


def _check(label, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail and not ok else ''}")


def _section_1_cleanup():
    demo_items = ["FG-MCP-001", "SA-ENCLOSURE-PAINTED", "SRV-POWDER-COATING", "RM-STEEL-SHEET",
                  "RM-ENCLOSURE-BLANK", "RM-CONTACTOR", "RM-MCB", "RM-COPPER-WIRE", "RM-SCREW-M6"]
    left = frappe.get_all("Item", filters={"name": ["in", demo_items]}, pluck="name")
    _check("1  demo sample items removed", not left, left)
    sup = frappe.get_all("Supplier", filters={"name": ["in", ["Precision Metals Pvt Ltd", "Bharat Electricals",
                                                               "Sunrise Powder Coaters"]]}, pluck="name")
    _check("1  demo suppliers removed", not sup, sup)
    _check("1  demo project removed", not frappe.db.exists("Project", {"project_name": "Panel Line Commissioning"}))
    _check("1  'Assembly' operation kept", frappe.db.exists("Operation", "Assembly"))


def _section_2_1_settings():
    _check("2.1 perpetual inventory off",
           not frappe.db.get_value("Company", COMPANY, "enable_perpetual_inventory"))
    gl = frappe.db.count("GL Entry", {"is_cancelled": 0})
    _check("2.1 no active GL entries", gl == 0, f"{gl} active")
    v = frappe.db.get_single_value("Stock Settings", "valuation_method")
    _check("2.1 valuation method FIFO (open item)", v == "FIFO", v)
    bs = frappe.get_single("Buying Settings")
    _check("2.1 suppliers named by supplier name", bs.supp_master_name == "Supplier Name", bs.supp_master_name)
    _check("2.1 PO not required for receipt", bs.po_required == "No", bs.po_required)
    _check("2.1 Purchase Receipt not required", bs.pr_required == "No", bs.pr_required)
    _check("2.1 maintain same rate off", not bs.maintain_same_rate, bs.maintain_same_rate)


def _section_2_2_roles():
    from erpnext.satcom_p1_foundation import CUSTOM_ROLES, DEMO_USERS, ROLE_PROFILES

    for role in CUSTOM_ROLES:
        r = frappe.db.get_value("Role", role, ["desk_access", "disabled"], as_dict=True)
        _check(f"2.2 role {role} exists with desk access", r and r.desk_access and not r.disabled, r)
    for profile, wanted in ROLE_PROFILES.items():
        have = sorted(frappe.get_all("Has Role", filters={"parenttype": "Role Profile", "parent": profile},
                                     pluck="role"))
        _check(f"2.2 profile {profile} = {', '.join(wanted)}", have == sorted(wanted), have)
    for email, (_, profiles) in DEMO_USERS.items():
        wanted = sorted({r for p in profiles for r in ROLE_PROFILES[p]})
        have = sorted(set(frappe.get_roles(email)) - {"All", "Guest", "Desk User"})
        enabled = frappe.db.get_value("User", email, "enabled")
        _check(f"2.2 {email} holds {', '.join(profiles)}", enabled and have == wanted, f"have {have}")
    approvers = [e for e in DEMO_USERS if "Satcom Approver" in frappe.get_roles(e)]
    _check("2.2 at least two demo approvers", len(approvers) >= 2, approvers)


def _section_2_3_warehouses():
    active = {"Stores", "Quality Hold", "Rejected", "Work In Progress", "Finished Goods", "Repair RMA",
              "Subcontractor (Job Work)", "Scrap", "Goods In Transit"}
    for name in sorted(active):
        w = frappe.db.get_value("Warehouse", f"{name} - STPL", ["disabled", "is_group", "company"], as_dict=True)
        _check(f"2.3 {name} - STPL active", w and not w.disabled and not w.is_group and w.company == COMPANY, w)
    _check("2.3 Rejected - STPL flagged as rejected warehouse",
           frappe.db.get_value("Warehouse", "Rejected - STPL", "is_rejected_warehouse"))
    _check("2.3 Raw Material - STPL disabled", frappe.db.get_value("Warehouse", "Raw Material - STPL", "disabled"))


def _section_2_4_items():
    from erpnext.satcom_p1_foundation import ATTRIBUTES, ITEM_GROUPS, TEMPLATES

    for group, (prefix, code_type) in ITEM_GROUPS.items():
        g = frappe.db.get_value("Item Group", group, ["satcom_prefix", "satcom_code_type"], as_dict=True)
        _check(f"2.4 group {group} = {prefix} / {code_type}",
               g and g.satcom_prefix == prefix and g.satcom_code_type == code_type, g)
    for fieldname in ("satcom_mpn", "satcom_manufacturer", "satcom_drawing_no", "satcom_drawing_rev"):
        _check(f"2.4 Item field {fieldname}", frappe.db.exists("Custom Field", {"dt": "Item", "fieldname": fieldname}))
    for attribute, values in ATTRIBUTES.items():
        have = set(frappe.get_all("Item Attribute Value", filters={"parent": attribute}, pluck="abbr"))
        _check(f"2.4 attribute {attribute} has {', '.join(values)}", set(values) <= have, sorted(have))
    for code, (_, group, attributes) in TEMPLATES.items():
        t = frappe.db.get_value("Item", code, ["has_variants", "item_group", "has_batch_no"], as_dict=True)
        attrs = frappe.get_all("Item Variant Attribute", filters={"parent": code}, pluck="attribute", order_by="idx")
        _check(f"2.4 template {code} ({', '.join(attributes)})",
               t and t.has_variants and t.item_group == group and t.has_batch_no and attrs == attributes, (t, attrs))
    for name, event in (("Satcom Item - number", "Before Insert"), ("Satcom Item - rules", "Before Save")):
        s = frappe.db.get_value("Server Script", name, ["disabled", "doctype_event", "reference_doctype"], as_dict=True)
        _check(f"2.4 server script {name}", s and not s.disabled and s.doctype_event == event and s.reference_doctype == "Item", s)
    _check("2.4 client script Satcom Item", frappe.db.get_value("Client Script", "Satcom Item", "enabled"))
    copied = set(frappe.get_all("Variant Field", pluck="field_name"))
    _check("2.4 variants copy description, not the series",
           "description" in copied and not {"serial_no_series", "batch_number_series"} & copied)
    _check("2.4 New Item opens the full form", frappe.get_meta("Item").quick_entry == 0)
    collapsed = [f.fieldname for f in frappe.get_meta("Item").fields
                 if f.fieldname in ("section_break_11", "serial_nos_and_batches") and f.collapsible]
    _check("2.4 Description and Serial Nos / Batches sections open", not collapsed, collapsed)


def cleanup():
    """Remove DEMO test records (writes). Items: name or Manufacturer Part No starting with DEMO.
    Their Deleted Document rows go too, so test runs don't use up real item numbers."""
    items = sorted({i.name for i in frappe.get_all("Item", filters={"item_name": ["like", "DEMO%"]}, fields=["name"])}
                   | {i.name for i in frappe.get_all("Item", filters={"satcom_mpn": ["like", "DEMO%"]}, fields=["name"])})
    for name in items:
        frappe.delete_doc("Item", name)
        print(f"deleted Item {name}")
    if items:
        n = frappe.db.count("Deleted Document", {"deleted_doctype": "Item", "deleted_name": ["in", items]})
        frappe.db.delete("Deleted Document", {"deleted_doctype": "Item", "deleted_name": ["in", items]})
        print(f"removed {n} Deleted Document row(s)")
    frappe.db.commit()
    print(f"cleanup: {len(items)} DEMO item(s)")


def verify():
    _results.clear()
    _section_1_cleanup()
    _section_2_1_settings()
    _section_2_2_roles()
    _section_2_3_warehouses()
    _section_2_4_items()
    failed = _results.count(False)
    print(f"{len(_results) - failed}/{len(_results)} PASS" + (f", {failed} FAIL" if failed else ""))
