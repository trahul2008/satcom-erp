"""Phase 1 acceptance check for satcom-erp (SPEC_PHASE1.md section 10). Read-only.

    bench --site frontend execute erpnext.satcom_p1_check.verify
Prints PASS/FAIL per line and a summary. It grows with each section as it is built; the DEMO
scenario (create_demo / cleanup, spec section 10) is added once the sections it needs exist.
Built so far: 1 demo cleanup, 2.1 settings, 2.2 roles, 2.3 warehouses, 2.4 item codes, 2.5 jobs.
    bench --site frontend execute erpnext.satcom_p1_check.create_demo   (writes DEMO records)
    bench --site frontend execute erpnext.satcom_p1_check.cleanup       (removes them)
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
    from erpnext.satcom_p1_foundation import ATTRIBUTES, ITEM_GROUPS, PART_NO_OPTIONAL, TEMPLATES

    for group, (prefix, code_type) in ITEM_GROUPS.items():
        part_no = 0 if prefix in PART_NO_OPTIONAL else 1
        g = frappe.db.get_value("Item Group", group, ["satcom_prefix", "satcom_code_type", "satcom_part_no_required"],
                                as_dict=True)
        _check(f"2.4 group {group} = {prefix} / {code_type} / Part No {'required' if part_no else 'optional'}",
               g and g.satcom_prefix == prefix and g.satcom_code_type == code_type
               and int(g.satcom_part_no_required or 0) == part_no, g)
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


def _section_2_5_jobs():
    from erpnext.satcom_p1_foundation import JOB_TYPES

    meta = frappe.get_meta("Project")
    jt = meta.get_field("satcom_job_type")
    _check("2.5 Job Type field (required, set once)", jt and jt.reqd and jt.set_only_once
           and jt.options.split("\n")[1:] == JOB_TYPES, jt and jt.options)
    for f in ("satcom_job_title", "satcom_parent_job", "satcom_customer_po_no", "satcom_customer_po_date",
              "satcom_incoming_inspection", "satcom_certificates_required", "satcom_qc_notes"):
        _check(f"2.5 Project field {f}", meta.has_field(f))
    _check("2.5 Incoming Inspection defaults to Standard checks",
           meta.get_field("satcom_incoming_inspection").default == "Standard checks")
    pn = meta.get_field("project_name")
    _check("2.5 Job Code (project_name) read-only, not typed", pn.read_only and not pn.reqd)
    _check("2.5 New Project opens the full form", meta.quick_entry == 0)
    for name, event in (("Satcom Project - job code", "Before Insert"),
                        ("Satcom Project - job code check", "After Insert"),
                        ("Satcom Project - rules", "Before Save")):
        sc = frappe.db.get_value("Server Script", name, ["disabled", "doctype_event", "reference_doctype"], as_dict=True)
        _check(f"2.5 server script {name}", sc and not sc.disabled and sc.doctype_event == event
               and sc.reference_doctype == "Project", sc)
    for user, can in (("demo.indenter@example.com", True), ("demo.allroles@example.com", True),
                      ("demo.stores@example.com", False), ("demo.approver1@example.com", False)):
        has = bool(frappe.has_permission("Project", "create", user=user))
        _check(f"2.5 {user} {'can' if can else 'cannot'} create jobs", has == can, has)
    jobs = {p.satcom_job_title: p for p in frappe.get_all(
        "Project", filters={"satcom_job_title": ["like", "DEMO%"]},
        fields=["name", "project_name", "satcom_job_title", "satcom_parent_job"])}
    if jobs:
        yy = frappe.utils.nowdate()[2:4]
        for title, expected in ((DEMO_JOBS[0][0], f"J-{yy}-0001"), (DEMO_JOBS[1][0], f"S-{yy}-0001"),
                                (DEMO_JOBS[2][0], f"J-{yy}-0001-01")):
            j = jobs.get(title)
            _check(f"2.5 demo job \"{title}\" is {expected} (name = Job Code)",
                   j and j.name == expected and j.project_name == expected, j)


# DEMO scenario (spec section 10); built up section by section ---------------------------------

DEMO_CUSTOMER = "DEMO Customer"
# (title, job type, extra fields); the extension's parent is the first job
DEMO_JOBS = [
    ("DEMO customer order job", "Customer Order",
     {"customer": DEMO_CUSTOMER, "satcom_customer_po_no": "DEMO-PO-0001",
      "satcom_incoming_inspection": "100% inspection", "satcom_certificates_required": 1,
      "satcom_qc_notes": "DEMO: customer wants 100% visual check"}),
    ("DEMO stock build job", "Stock Build", {}),
    ("DEMO extension job", "Extension", {}),
]
INDENTER = "demo.indenter@example.com"


def _expect_block(label, fn):
    frappe.db.savepoint("demo_try")
    try:
        doc = fn()
        print(f"FAIL  {label}: not blocked ({doc.name})")
    except Exception as e:
        print(f"PASS  {label}: blocked: {frappe.utils.strip_html(str(e))[:160]}")
    frappe.db.rollback(save_point="demo_try")
    frappe.local.message_log = []


def create_demo():
    """Build the DEMO records for what's been built so far (writes). Run cleanup() first to redo."""
    if frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]}, limit=1):
        frappe.throw("DEMO jobs exist; run cleanup first")
    if not frappe.db.exists("Customer", DEMO_CUSTOMER):
        frappe.get_doc({"doctype": "Customer", "customer_name": DEMO_CUSTOMER, "customer_type": "Company",
                        "customer_group": "Commercial", "territory": "India"}).insert()
    today = frappe.utils.nowdate()
    frappe.set_user(INDENTER)
    try:
        made = []
        for title, job_type, extra in DEMO_JOBS:
            values = {"doctype": "Project", "company": COMPANY, "satcom_job_type": job_type,
                      "satcom_job_title": title, **extra}
            if job_type == "Customer Order":
                values["satcom_customer_po_date"] = today
            if job_type == "Extension":
                values["satcom_parent_job"] = made[0]
            doc = frappe.get_doc(values).insert()
            made.append(doc.name)
            print(f"job {doc.name} ({job_type}) project_name={doc.project_name} by {INDENTER}")

        def job(**v):
            return frappe.get_doc({"doctype": "Project", "company": COMPANY, "satcom_job_title": "DEMO try", **v})
        _expect_block("Customer Order without PO", lambda: job(satcom_job_type="Customer Order",
                                                              customer=DEMO_CUSTOMER).insert())
        _expect_block("Extension without parent", lambda: job(satcom_job_type="Extension").insert())
        _expect_block("Extension of an extension", lambda: job(satcom_job_type="Extension",
                                                              satcom_parent_job=made[2]).insert())
        _expect_block("no job type", lambda: job().insert())
        _expect_block("Job Code edited", lambda: frappe.get_doc("Project", made[1]).update(
            {"project_name": "S-99-9999"}).save())
        _expect_block("Job Type changed later", lambda: frappe.get_doc("Project", made[1]).update(
            {"satcom_job_type": "Customer Order"}).save())
        frappe.set_user("demo.stores@example.com")
        _expect_block("stores user creates a job", lambda: job(satcom_job_type="Stock Build").insert())
    finally:
        frappe.set_user("Administrator")
    frappe.db.commit()


def _restore_series(prefixes):
    """After deleting DEMO records, set each counter back to the highest number still in use."""
    for prefix in prefixes:
        rows = frappe.db.sql("select current from tabSeries where name=%s", prefix)
        if not rows:
            continue
        digits = 2 if prefix.count("-") > 2 else 4
        used = frappe.db.sql(
            "select max(cast(substring(name, %s) as unsigned)) from tabProject where name regexp %s",
            (len(prefix) + 1, "^" + prefix + "[0-9]{" + str(digits) + "}$"))[0][0] or 0
        if used != rows[0][0]:
            frappe.db.sql("update tabSeries set current=%s where name=%s", (used, prefix))
            print(f"counter {prefix}: {rows[0][0]} -> {used}")


def cleanup():
    """Remove DEMO test records (writes): items whose name or MPN starts with DEMO, DEMO jobs and
    the DEMO customer. Their Deleted Document rows go too, and job counters go back to the highest
    number still in use, so test runs don't use up real item or job numbers."""
    items = sorted({i.name for i in frappe.get_all("Item", filters={"item_name": ["like", "DEMO%"]}, fields=["name"])}
                   | {i.name for i in frappe.get_all("Item", filters={"satcom_mpn": ["like", "DEMO%"]}, fields=["name"])})
    jobs = frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]},
                          fields=["name", "satcom_job_type"], order_by="name desc")
    jobs.sort(key=lambda j: j.satcom_job_type != "Extension")  # extensions before their parents
    deleted = {"Item": items, "Project": [j.name for j in jobs], "Customer": []}
    for name in items:
        frappe.delete_doc("Item", name)
        print(f"deleted Item {name}")
    for j in jobs:
        frappe.delete_doc("Project", j.name)
        print(f"deleted Project {j.name}")
    if frappe.db.exists("Customer", DEMO_CUSTOMER):
        frappe.delete_doc("Customer", DEMO_CUSTOMER)
        deleted["Customer"].append(DEMO_CUSTOMER)
        print(f"deleted Customer {DEMO_CUSTOMER}")
    for dt, names in deleted.items():
        if names:
            frappe.db.delete("Deleted Document", {"deleted_doctype": dt, "deleted_name": ["in", names]})
    yy = frappe.utils.nowdate()[2:4]
    _restore_series([f"J-{yy}-", f"S-{yy}-"] + [j.name + "-" for j in jobs])
    frappe.db.commit()
    print(f"cleanup: {len(items)} item(s), {len(jobs)} job(s), {len(deleted['Customer'])} customer(s)")


def verify():
    _results.clear()
    _section_1_cleanup()
    _section_2_1_settings()
    _section_2_2_roles()
    _section_2_3_warehouses()
    _section_2_4_items()
    _section_2_5_jobs()
    failed = _results.count(False)
    print(f"{len(_results) - failed}/{len(_results)} PASS" + (f", {failed} FAIL" if failed else ""))
