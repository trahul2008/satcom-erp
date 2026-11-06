"""Phase 1 acceptance check for satcom-erp (SPEC_PHASE1.md section 10). Read-only.

    bench --site frontend execute erpnext.satcom_p1_check.verify
Prints PASS/FAIL per line and a summary. It grows with each section as it is built; the DEMO
scenario (create_demo / cleanup, spec section 10) is added once the sections it needs exist.
Built so far: 1 demo cleanup, 2.1 settings, 2.2 roles, 2.3 warehouses, 2.4 item codes, 2.5 jobs, 3 indents.
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
    _check("2.5 job pickers show the Job Title", "satcom_job_title" in (meta.search_fields or ""), meta.search_fields)
    order = [d.fieldname for d in meta.fields]
    _check("2.5 Customer sits before the PO fields",
           order.index("customer") == order.index("satcom_customer_po_no") - 1)
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


DEMO_ITEMS = [  # (code prefix, item name, group, extra) - created as Administrator (stores' job)
    ("RFC", "DEMO RF amplifier", "RF Components", {"satcom_mpn": "DEMO-RF-0001", "has_serial_no": 1}),
    ("TOL", "DEMO crimp tool", "Tools & Spares", {"has_serial_no": 1}),
]
APPROVER, APPROVER_2 = "demo.approver1@example.com", "demo.approver2@example.com"
ALL_ROLES, STORES = "demo.allroles@example.com", "demo.stores@example.com"


def _expect_block(label, fn):
    frappe.db.savepoint("demo_try")
    try:
        doc = fn()
        print(f"FAIL  {label}: not blocked ({getattr(doc, 'name', doc)})")
    except Exception as e:
        print(f"PASS  {label}: blocked: {frappe.utils.strip_html(str(e))[:160]}")
    frappe.db.rollback(save_point="demo_try")
    frappe.local.message_log = []


def _as(user, fn):
    frappe.set_user(user)
    try:
        return fn()
    finally:
        frappe.set_user("Administrator")


def _indent(title, job, item, qty=2):
    return frappe.get_doc({
        "doctype": "Material Request", "material_request_type": "Purchase", "company": COMPANY,
        "title": title, "satcom_job": job, "schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7),
        "items": [{"item_code": item, "qty": qty, "warehouse": "Stores - STPL",
                   "schedule_date": frappe.utils.add_days(frappe.utils.nowdate(), 7)}]})


def create_demo():
    """Build the DEMO records for what's been built so far (writes). Run cleanup() first to redo."""
    from frappe.model.workflow import apply_workflow

    if frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]}, limit=1):
        frappe.throw("DEMO jobs exist; run cleanup first")
    today = frappe.utils.nowdate()

    # 2.5 jobs (the Customer itself is made by the indenter: spec 2.5 lets indenters create customers)
    made = []

    def make_jobs():
        frappe.get_doc({"doctype": "Customer", "customer_name": DEMO_CUSTOMER, "customer_type": "Company",
                        "customer_group": "Commercial", "territory": "India", "tax_id": "DEMOGSTIN0000Z0"}).insert()
        print(f"customer {DEMO_CUSTOMER} by {INDENTER}")
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
    _as(INDENTER, make_jobs)
    _as(STORES, lambda: _expect_block("stores user creates a job", lambda: frappe.get_doc({
        "doctype": "Project", "company": COMPANY, "satcom_job_type": "Stock Build",
        "satcom_job_title": "DEMO try"}).insert()))

    # items for the indents (stores creates items; here Administrator)
    codes = {}
    for prefix, name, group, extra in DEMO_ITEMS:
        it = frappe.get_doc({"doctype": "Item", "item_code": prefix, "item_name": name, "item_group": group,
                             "stock_uom": "Nos", "is_stock_item": 1, "description": name, **extra}).insert()
        codes[prefix] = it.name
        print(f"item {it.name} ({name})")

    # 3 indents
    def raise_and_send(user, title, job, item):
        def go():
            mr = _indent(title, job, item).insert()
            mr = apply_workflow(mr, "Submit for Approval")
            return mr.name
        name = _as(user, go)
        print(f"indent {name} '{title}' by {user}: {frappe.db.get_value('Material Request', name, 'workflow_state')}")
        return name

    a = raise_and_send(INDENTER, "DEMO indent for the customer order", made[0], codes["RFC"])
    _as(STORES, lambda: _expect_block("stores user approves", lambda: apply_workflow(
        frappe.get_doc("Material Request", a), "Approve")))
    _as(APPROVER, lambda: apply_workflow(frappe.get_doc("Material Request", a), "Approve"))
    mr = frappe.get_doc("Material Request", a)
    print(f"indent {a} approved by {APPROVER}: state={mr.workflow_state} docstatus={mr.docstatus} "
          f"rows project={[r.project for r in mr.items]}")

    b = raise_and_send(INDENTER, "DEMO tools indent, no job", None, codes["TOL"])
    _as(APPROVER_2, lambda: _expect_block("reject without a reason", lambda: apply_workflow(
        frappe.get_doc("Material Request", b), "Reject")))

    def reject_with_reason():
        doc = frappe.get_doc("Material Request", b)
        doc.satcom_rejection_reason = "DEMO: tools are in stock"
        doc.save()
        return apply_workflow(frappe.get_doc("Material Request", b), "Reject")
    _as(APPROVER_2, reject_with_reason)
    print(f"indent {b} rejected by {APPROVER_2}: {frappe.db.get_value('Material Request', b, 'workflow_state')}")

    c = raise_and_send(ALL_ROLES, "DEMO self-approval try", made[1], codes["RFC"])
    _as(ALL_ROLES, lambda: _expect_block("approver approves own indent", lambda: apply_workflow(
        frappe.get_doc("Material Request", c), "Approve")))
    _as(ALL_ROLES, lambda: _expect_block("approver submits own indent directly", lambda: frappe.get_doc(
        "Material Request", c).submit()))

    d = raise_and_send(INDENTER, "DEMO indent to cancel", made[0], codes["RFC"])
    _as(APPROVER, lambda: apply_workflow(frappe.get_doc("Material Request", d), "Approve"))
    _as(INDENTER, lambda: _expect_block("indenter cancels an approved indent", lambda: frappe.get_doc(
        "Material Request", d).cancel()))
    _as(APPROVER, lambda: _expect_block("approver cancels without a reason", lambda: frappe.get_doc(
        "Material Request", d).cancel()))

    def cancel_with_reason():
        frappe.db.set_value("Material Request", d, "satcom_cancel_reason", "DEMO: quantity changed")
        return frappe.get_doc("Material Request", d).cancel()
    _as(APPROVER, cancel_with_reason)
    print(f"indent {d} cancelled by {APPROVER}: {frappe.db.get_value('Material Request', d, 'workflow_state')}")

    _as(INDENTER, lambda: _expect_block("indent without a job (RF part)", lambda: _indent(
        "DEMO try", None, codes["RFC"]).insert()))

    def direct_submit():
        mr = _indent("DEMO try", made[0], codes["RFC"]).insert()
        return mr.submit()
    _as(INDENTER, lambda: _expect_block("indenter submits a draft directly (bypass)", direct_submit))
    _as(STORES, lambda: _expect_block("stores submits a draft directly (bypass)", direct_submit))
    frappe.db.commit()


def _restore_series(prefixes, table="tabProject"):
    """After deleting DEMO records, set each counter back to the highest number still in use."""
    for prefix in prefixes:
        rows = frappe.db.sql("select current from tabSeries where name=%s", prefix)
        if not rows:
            continue
        digits = 2 if table == "tabProject" and prefix.count("-") > 2 else (4 if table == "tabProject" else 5)
        used = frappe.db.sql(
            f"select max(cast(substring(name, %s) as unsigned)) from `{table}` where name regexp %s",
            (len(prefix) + 1, "^" + prefix + "[0-9]{" + str(digits) + "}$"))[0][0] or 0
        if used != rows[0][0]:
            frappe.db.sql("update tabSeries set current=%s where name=%s", (used, prefix))
            print(f"counter {prefix}: {rows[0][0]} -> {used}")


def cleanup():
    """Remove DEMO test records (writes): DEMO indents, items whose name or MPN starts with DEMO,
    DEMO jobs and the DEMO customer, with their notifications and Deleted Document rows. Counters go
    back to the highest number still in use, so test runs don't use up real numbers."""
    # DEMO indents: titled DEMO, or for a DEMO job, or holding a DEMO item (forms title them themselves)
    demo_jobs = frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]}, pluck="name")
    demo_items = frappe.get_all("Item", filters={"item_name": ["like", "DEMO%"]}, pluck="name")
    names = set(frappe.get_all("Material Request", filters={"title": ["like", "DEMO%"]}, pluck="name"))
    if demo_jobs:
        names |= set(frappe.get_all("Material Request", filters={"satcom_job": ["in", demo_jobs]}, pluck="name"))
    if demo_items:
        names |= set(frappe.get_all("Material Request Item", filters={"item_code": ["in", demo_items]},
                                    pluck="parent"))
    indents = frappe.get_all("Material Request", filters={"name": ["in", list(names) or [""]]},
                             fields=["name", "docstatus"], order_by="name desc")
    for mr in indents:
        if mr.docstatus == 1:
            frappe.db.set_value("Material Request", mr.name, "satcom_cancel_reason", "DEMO cleanup")
            frappe.get_doc("Material Request", mr.name).cancel()
        for dt, field in (("Workflow Action", "reference_name"), ("Notification Log", "document_name")):
            frappe.db.delete(dt, {field: mr.name})
        frappe.delete_doc("Material Request", mr.name)
        print(f"deleted Material Request {mr.name}")
    items = sorted({i.name for i in frappe.get_all("Item", filters={"item_name": ["like", "DEMO%"]}, fields=["name"])}
                   | {i.name for i in frappe.get_all("Item", filters={"satcom_mpn": ["like", "DEMO%"]}, fields=["name"])})
    jobs = frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]},
                          fields=["name", "satcom_job_type"], order_by="name desc")
    jobs.sort(key=lambda j: j.satcom_job_type != "Extension")  # extensions before their parents
    deleted = {"Material Request": [m.name for m in indents], "Item": items,
               "Project": [j.name for j in jobs], "Customer": []}
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
    _restore_series([f"MAT-MR-{frappe.utils.nowdate()[:4]}-"], table="tabMaterial Request")
    frappe.db.commit()
    print(f"cleanup: {len(indents)} indent(s), {len(items)} item(s), {len(jobs)} job(s), "
          f"{len(deleted['Customer'])} customer(s)")


def _section_3_indents():
    from erpnext.satcom_p1_purchase import INDENT_GRID, INDENT_STATES, INDENT_TRANSITIONS, INDENT_WORKFLOW, NOTIFICATIONS

    # 2.5 addendum (spec 9467f55): who can create customers, who can read jobs and customers
    for user, ptype, dt, can in ((INDENTER, "create", "Customer", True), (STORES, "create", "Customer", False),
                                 (STORES, "read", "Project", True), (APPROVER, "read", "Project", True),
                                 (STORES, "read", "Customer", True), (APPROVER, "read", "Customer", True)):
        has = bool(frappe.has_permission(dt, ptype, user=user))
        _check(f"2.5 {user} {'can' if can else 'cannot'} {ptype} {dt}", has == can, has)
    meta = frappe.get_meta("Material Request")
    _check("3 Material Request fields satcom_job, satcom_rejection_reason",
           meta.has_field("satcom_job") and meta.has_field("satcom_rejection_reason"))
    for name, event in (("Satcom Indent - rules", "Before Save"), ("Satcom Indent - approval guard", "Before Submit"),
                        ("Satcom Indent - cancel guard", "Before Cancel")):
        sc = frappe.db.get_value("Server Script", name, ["disabled", "doctype_event"], as_dict=True)
        _check(f"3 server script {name}", sc and not sc.disabled and sc.doctype_event == event, sc)
    _check("3 client script Satcom Indent (reason dialogs)", frappe.db.get_value("Client Script", "Satcom Indent", "enabled"))
    _check("3 header Required By is mandatory", meta.get_field("schedule_date").reqd)
    _check("3 Cancel Reason field (editable after submit)",
           meta.has_field("satcom_cancel_reason") and meta.get_field("satcom_cancel_reason").allow_on_submit)
    wf = frappe.get_doc("Workflow", INDENT_WORKFLOW) if frappe.db.exists("Workflow", INDENT_WORKFLOW) else None
    _check(f"3 workflow {INDENT_WORKFLOW} active on Material Request, no email",
           wf and wf.is_active and wf.document_type == "Material Request" and not wf.send_email_alert)
    if wf:
        _check("3 workflow states", [(s.state, s.doc_status, s.allow_edit) for s in wf.states]
               == [(s, d, r) for s, (d, r, _) in INDENT_STATES.items()])
        _check("3 workflow transitions (Approve: no self approval)",
               [(t.state, t.action, t.next_state, t.allowed, t.allow_self_approval) for t in wf.transitions]
               == [tuple(t) for t in INDENT_TRANSITIONS])
    for name in NOTIFICATIONS:
        _check(f"3 notification {name}", frappe.db.get_value("Notification", name, "enabled"))
    grid = frappe.get_meta("Material Request Item")
    _check("3 indent grid shows stock in hand and projected qty",
           all(grid.get_field(fn).in_list_view for fn in INDENT_GRID)
           and sum(grid.get_field(fn).columns or 0 for fn in INDENT_GRID) <= 10
           and not grid.get_field("schedule_date").in_list_view)

    demo = {m.title: m for m in frappe.get_all("Material Request", filters={"title": ["like", "DEMO%"]},
                                               fields=["name", "title", "workflow_state", "docstatus", "satcom_job",
                                                       "owner", "satcom_rejection_reason"])}
    if demo:
        a = demo.get("DEMO indent for the customer order")
        rows = frappe.get_all("Material Request Item", filters={"parent": a.name}, pluck="project") if a else []
        _check("3 demo indent approved by an approver and submitted, rows carry the job",
               a and a.workflow_state == "Approved" and a.docstatus == 1 and rows and set(rows) == {a.satcom_job}, a)
        b = demo.get("DEMO tools indent, no job")
        _check("3 demo tools indent without a job, rejected with a reason",
               b and not b.satcom_job and b.workflow_state == "Rejected" and b.satcom_rejection_reason, b)
        c = demo.get("DEMO self-approval try")
        _check("3 demo self-approval stays pending", c and c.workflow_state == "Pending Approval" and c.docstatus == 0, c)
        x = demo.get("DEMO indent to cancel")
        _check("3 demo approved indent cancelled by an approver with a reason",
               x and x.workflow_state == "Cancelled" and x.docstatus == 2
               and frappe.db.get_value("Material Request", x.name, "satcom_cancel_reason"), x)
        for mr, user in ((a, APPROVER), (a, INDENTER), (b, INDENTER)):
            n = frappe.db.count("Notification Log", {"document_type": "Material Request",
                                                     "document_name": mr.name, "for_user": user}) if mr else 0
            _check(f"3 in-app notification for {user} on {mr and mr.name}", n > 0, n)


def verify():
    _results.clear()
    _section_1_cleanup()
    _section_2_1_settings()
    _section_2_2_roles()
    _section_2_3_warehouses()
    _section_2_4_items()
    _section_2_5_jobs()
    _section_3_indents()
    failed = _results.count(False)
    print(f"{len(_results) - failed}/{len(_results)} PASS" + (f", {failed} FAIL" if failed else ""))
