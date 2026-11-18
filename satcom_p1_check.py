"""Phase 1 acceptance check for satcom-erp (SPEC_PHASE1.md section 10). Read-only.

    bench --site frontend execute erpnext.satcom_p1_check.verify
Prints PASS/FAIL per line and a summary. It grows with each section as it is built; the DEMO
scenario (create_demo / cleanup, spec section 10) is added once the sections it needs exist.
Built so far: 1 demo cleanup, 2.1 settings, 2.2 roles, 2.3 warehouses, 2.4 item codes, 2.5 jobs, 3 indents,
4 quotations and purchase orders, 5 receipt and QC.
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
    # "Purchase Order Required" is checked in section 4 (Yes once section 4 is live, spec 5.1)
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


DEMO_SUPPLIER = "DEMO Supplier"
QC_USER = "demo.qc@example.com"
QH, REJECTED, STORES_WH, SCRAP_WH = "Quality Hold - STPL", "Rejected - STPL", "Stores - STPL", "Scrap - STPL"
SERIES_KEY = "satcom_demo_series"


def _file(doctype, name, file_name, text):
    return frappe.get_doc({"doctype": "File", "file_name": file_name, "content": text, "is_private": 1,
                           "attached_to_doctype": doctype, "attached_to_name": name}).insert()


def _grn(rows, **over):
    today = frappe.utils.nowdate()
    values = {"doctype": "Purchase Receipt", "company": COMPANY, "supplier": DEMO_SUPPLIER, "posting_date": today,
              "satcom_vendor_invoice_no": "DEMO-INV-0001", "satcom_vendor_invoice_date": today,
              "satcom_vendor_dc_no": "DEMO-DC-0001", "satcom_vendor_dc_date": today,
              "items": [{"item_code": i, "qty": q, "rate": 100, "project": j, "warehouse": w or QH} for i, q, j, w in rows]}
    values.update(over)
    return frappe.get_doc(values)


def _transfer(rows, **over):
    """rows: (item, qty, serial or None, batch or None, from, to)"""
    values = {"doctype": "Stock Entry", "company": COMPANY, "stock_entry_type": "Material Transfer",
              "items": [{"item_code": i, "qty": q, "s_warehouse": s, "t_warehouse": t, "use_serial_batch_fields": 1,
                         "serial_no": sn, "batch_no": bn} for i, q, sn, bn, s, t in rows]}
    values.update(over)
    return frappe.get_doc(values)


# Section 4 demo: three suppliers to quote; every DEMO PO carries a label in Order Confirmation No
DEMO_SUPPLIERS = [DEMO_SUPPLIER, "DEMO Supplier 2", "DEMO Supplier 3"]
PO_LABEL = "order_confirmation_no"


def _demo_suppliers():
    for name in DEMO_SUPPLIERS:
        if not frappe.db.exists("Supplier", name):
            frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_group": "Raw Material",
                            "supplier_type": "Company"}).insert()


def _quotation(supplier, item, qty, rate):
    today = frappe.utils.nowdate()
    return frappe.get_doc({"doctype": "Supplier Quotation", "company": COMPANY, "supplier": supplier,
                           "transaction_date": today, "valid_till": frappe.utils.add_days(today, 30),
                           "items": [{"item_code": item, "qty": qty, "rate": rate}]})


def _po(label, rows, quotations=(), **over):
    """rows: (item, qty, rate, job). Rows go to Quality Hold, so the GRN made from the PO lands there."""
    today = frappe.utils.nowdate()
    due = frappe.utils.add_days(today, 7)
    values = {"doctype": "Purchase Order", "company": COMPANY, "supplier": DEMO_SUPPLIER, "transaction_date": today,
              "schedule_date": due, PO_LABEL: label,
              "items": [{"item_code": i, "qty": q, "rate": r, "project": j, "schedule_date": due, "warehouse": QH}
                        for i, q, r, j in rows],
              "satcom_quotations": [{"supplier_quotation": q} for q in quotations]}
    values.update(over)
    return frappe.get_doc(values)


def _raise_po(user, label, rows, quotations=(), **over):
    """Insert a DEMO PO as `user` and send it for approval; returns its name."""
    from frappe.model.workflow import apply_workflow

    def go():
        po = _po(label, rows, quotations, **over).insert()
        return apply_workflow(po, "Submit for Approval").name
    name = _as(user, go)
    print(f"PO {name} '{label}' by {user}: {frappe.db.get_value('Purchase Order', name, 'workflow_state')}, "
          f"net {frappe.db.get_value('Purchase Order', name, 'base_net_total')}")
    return name


def _approve_po(name, user=None):
    from frappe.model.workflow import apply_workflow

    _as(user or APPROVER, lambda: apply_workflow(frappe.get_doc("Purchase Order", name), "Approve"))
    print(f"PO {name} approved by {user or APPROVER}: "
          f"{frappe.db.get_value('Purchase Order', name, ['workflow_state', 'docstatus'])}")


def _demo_purchase_orders(made, codes, indent):
    """Section 4 (spec 10.4): the quotation rule at Rs 4,00,000 (too few quotations, the same
    supplier twice, a draft quotation, three suppliers, an approver's waiver), a Rs 50,000 tools PO
    with no job and no quotations, the approval workflow (reject with a reason, no self approval,
    no direct submit), the job rule, and a PO made from the approved indent. Purchase = demo.indenter."""
    from erpnext.stock.doctype.material_request.material_request import make_purchase_order
    from frappe.model.workflow import apply_workflow

    rfc, tol, job = codes["RFC"], codes["TOL"], made[0]
    big = [(rfc, 4, 100000, job)]  # Rs 4,00,000 net
    _demo_suppliers()

    def quotes():
        out = []
        for supplier in [*DEMO_SUPPLIERS, DEMO_SUPPLIER]:  # the 4th: a second quotation from supplier 1
            q = _quotation(supplier, rfc, 4, 100000).insert()
            q.submit()
            out.append(q.name)
        out.append(_quotation(DEMO_SUPPLIERS[2], rfc, 4, 100000).insert().name)  # the 5th stays a draft
        return out
    q = _as(INDENTER, quotes)
    print(f"supplier quotations by {INDENTER}: " + ", ".join(
        f"{n} ({frappe.db.get_value('Supplier Quotation', n, 'supplier')}, "
        f"docstatus {frappe.db.get_value('Supplier Quotation', n, 'docstatus')})" for n in q))
    print(f"Satcom Settings: threshold {frappe.db.get_single_value('Satcom Settings', 'quotation_threshold')}, "
          f"min {frappe.db.get_single_value('Satcom Settings', 'min_quotations')}, "
          f"basis {frappe.db.get_single_value('Satcom Settings', 'threshold_basis')}")

    # 4.2 job rule and the bypass
    _as(INDENTER, lambda: _expect_block("PO row without a job (RF part)", lambda: _po(
        "DEMO try", [(rfc, 1, 100, None)]).insert()))
    _as(INDENTER, lambda: _expect_block("purchase submits a draft PO directly (bypass)", lambda: _po(
        "DEMO try", [(rfc, 1, 100, job)]).insert().submit()))
    _as(INDENTER, lambda: _expect_block("non-approver waives the quotation rule", lambda: _po(
        "DEMO try", big, [q[0]], satcom_quote_waived=1, satcom_waiver_reason="DEMO").insert()))

    # 4.1 Rs 4,00,000 with two quotations: blocked, then rejected with a reason
    a = _raise_po(INDENTER, "DEMO-4L-2Q", big, [q[0], q[1]])
    _as(APPROVER, lambda: _expect_block("Rs 4,00,000 PO with 2 quotations approved", lambda: apply_workflow(
        frappe.get_doc("Purchase Order", a), "Approve")))
    _as(APPROVER, lambda: _expect_block("PO rejected without a reason", lambda: apply_workflow(
        frappe.get_doc("Purchase Order", a), "Reject")))

    def reject_with_reason():
        doc = frappe.get_doc("Purchase Order", a)
        doc.satcom_rejection_reason = "DEMO: only two quotations"
        doc.save()
        return apply_workflow(frappe.get_doc("Purchase Order", a), "Reject")
    _as(APPROVER, reject_with_reason)
    print(f"PO {a} rejected by {APPROVER}: {frappe.db.get_value('Purchase Order', a, 'workflow_state')}")

    # three submitted quotations but only two suppliers, plus a draft from the third: still blocked
    b = _raise_po(INDENTER, "DEMO-4L-SAME", big, [q[0], q[3], q[1], q[4]])
    sup = frappe.get_all("Satcom PO Quotation", filters={"parent": b}, pluck="supplier", order_by="idx")
    print(f"PO {b} quotation rows, supplier filled in: {sup}")
    _as(APPROVER, lambda: _expect_block("Rs 4,00,000 PO with 3 quotations from 2 suppliers and a draft approved",
                                        lambda: apply_workflow(frappe.get_doc("Purchase Order", b), "Approve")))

    # three different suppliers: passes
    c = _raise_po(INDENTER, "DEMO-4L-3Q", big, [q[0], q[1], q[2]])
    _as(INDENTER, lambda: _expect_block("purchase approves a PO", lambda: apply_workflow(
        frappe.get_doc("Purchase Order", c), "Approve")))
    _approve_po(c)

    # one quotation, waived by the approver with a reason: passes
    d = _raise_po(INDENTER, "DEMO-4L-WAIVED", big, [q[0]])

    def waive(reason):
        doc = frappe.get_doc("Purchase Order", d)
        doc.satcom_quote_waived = 1
        doc.satcom_waiver_reason = reason
        return doc.save()
    _as(APPROVER, lambda: _expect_block("waiver without a reason", lambda: waive("")))
    _as(APPROVER, lambda: waive("DEMO: single-source part"))
    _approve_po(d)

    # Rs 50,000 of tools: no job, no quotations
    e = _raise_po(INDENTER, "DEMO-50K-TOOLS", [(tol, 1, 50000, None)])
    _approve_po(e, APPROVER_2)

    # no self approval
    s = _raise_po(ALL_ROLES, "DEMO-SELF", [(rfc, 1, 100, job)])
    _as(ALL_ROLES, lambda: _expect_block("approver approves own PO", lambda: apply_workflow(
        frappe.get_doc("Purchase Order", s), "Approve")))
    _as(ALL_ROLES, lambda: _expect_block("approver submits own PO directly", lambda: frappe.get_doc(
        "Purchase Order", s).submit()))

    # the job flows from the approved indent's rows
    def from_indent():
        po = make_purchase_order(indent)
        po.supplier = DEMO_SUPPLIER
        po.set(PO_LABEL, "DEMO-FROM-INDENT")
        for row in po.items:
            row.rate = 100
        po.insert()
        return apply_workflow(po, "Submit for Approval").name
    g = _as(INDENTER, from_indent)
    _approve_po(g)
    print(f"PO {g} from indent {indent}: rows project="
          f"{frappe.get_all('Purchase Order Item', filters={'parent': g}, pluck='project')}, delivery address "
          f"{frappe.db.get_value('Purchase Order', g, 'shipping_address')}")


def _grn_from_po(po, **over):
    """The GRN stores makes from an approved PO (Create > Purchase Receipt), vendor documents filled in."""
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

    today = frappe.utils.nowdate()
    pr = make_purchase_receipt(po)
    pr.update({"posting_date": today, "satcom_vendor_invoice_no": "DEMO-INV-0001", "satcom_vendor_invoice_date": today,
               "satcom_vendor_dc_no": "DEMO-DC-0001", "satcom_vendor_dc_date": today})
    pr.update(over)
    return pr


def _demo_receipt_qc(made, codes):
    """Section 5: GRN from an approved PO into Quality Hold, Pending QC, QC release (accepted and
    rejected), the QC release rules, and each disposition. Stores = demo.stores, QC = demo.qc."""
    from erpnext.controllers.sales_and_purchase_return import make_return_doc
    from erpnext.satcom_p1_receipt_qc import PENDING_QC_SQL

    _demo_suppliers()
    con = frappe.get_doc({"doctype": "Item", "item_code": "CON", "item_name": "DEMO SMA connector",
                          "item_group": "Connectors", "stock_uom": "Nos", "is_stock_item": 1,
                          "description": "DEMO SMA connector", "satcom_mpn": "DEMO-CON-0001", "has_batch_no": 1}).insert()
    codes["CON"] = con.name
    rfc = codes["RFC"]
    job_cert, job_stock = made[0], made[1]  # J: 100% inspection + certificates; S: stock build
    print(f"item {con.name} (batch) qi_template={con.quality_inspection_template}; "
          f"RF item {rfc} qi_template={frappe.db.get_value('Item', rfc, 'quality_inspection_template')}")

    # 4 -> 5.1: the PO the GRN is made from (under the threshold: no quotations needed)
    po = _raise_po(INDENTER, "DEMO-GRN", [(rfc, 4, 100, job_cert), (con.name, 10, 100, job_stock)])
    _approve_po(po)

    # 5.1 GRN (stores)
    def blocks():
        _expect_block("GRN without a purchase order", lambda: _grn([(rfc, 1, job_cert, None)]).insert())

        def to_stores():
            pr = _grn_from_po(po)
            pr.items[0].warehouse = STORES_WH
            return pr.insert()
        _expect_block("GRN row to Stores (not Quality Hold)", to_stores)

        def no_job():
            pr = _grn_from_po(po)
            pr.items[0].project = None
            return pr.insert()
        _expect_block("GRN row without the PO row's job (RF part)", no_job)
        _expect_block("GRN submit without the invoice / DC scan", lambda: _grn_from_po(po).insert().submit())

        def no_invoice():
            pr = _grn_from_po(po, satcom_vendor_invoice_no="").insert()
            _file("Purchase Receipt", pr.name, "DEMO-scan.txt", "DEMO scan")
            return pr.submit()
        _expect_block("GRN submit without the vendor invoice no", no_invoice)

    _as(STORES, blocks)

    def receive():
        pr = _grn_from_po(po).insert()
        _file("Purchase Receipt", pr.name, "DEMO-invoice-and-dc.txt", "DEMO invoice / DC scan")
        pr.submit()
        return pr.name
    grn = _as(STORES, receive)
    serials = frappe.get_all("Serial No", filters={"item_code": rfc}, fields=["name", "warehouse", "satcom_received_for_job"],
                             order_by="name")
    batches = frappe.get_all("Batch", filters={"item": con.name}, fields=["name", "satcom_received_for_job"])
    print(f"GRN {grn} by {STORES}: serials {[(s.name, s.warehouse, s.satcom_received_for_job) for s in serials]}; "
          f"batches {[(b.name, b.satcom_received_for_job) for b in batches]}")
    pending = frappe.db.sql(PENDING_QC_SQL, as_dict=True)
    print(f"Pending QC: {len(pending)} line(s): " + "; ".join(
        f"{p['Serial / Batch:Data:180']} x{p['Qty:Float:70']} job {p['Job:Link/Project:110']} "
        f"{p['Days Waiting:Int:100']} d" for p in pending))

    # 5.2 QC release (QC user): 1 serial and the batch accepted, 3 serials rejected
    s = [x.name for x in serials]
    batch = batches[0].name

    def release_draft():
        se = _transfer([(rfc, 1, s[0], None, QH, STORES_WH), (rfc, 1, s[1], None, QH, REJECTED),
                        (rfc, 1, s[2], None, QH, REJECTED), (rfc, 1, s[3], None, QH, REJECTED),
                        (con.name, 10, None, batch, QH, STORES_WH)], stock_entry_type="QC Release").insert()
        return se.name
    se_name = _as(QC_USER, release_draft)
    se = frappe.get_doc("Stock Entry", se_name)
    print(f"QC release {se_name} draft by {QC_USER}: inspection_required={se.inspection_required} "
          f"rows project={[r.project for r in se.items]}")
    _as(QC_USER, lambda: _expect_block("QC release submitted without inspections",
                                       lambda: frappe.get_doc("Stock Entry", se_name).submit()))

    def inspect():
        for row, status in zip(se.items, ["Accepted", "Rejected", "Rejected", "Rejected", "Accepted"]):
            qi = frappe.get_doc({"doctype": "Quality Inspection", "inspection_type": "Outgoing",
                                 "reference_type": "Stock Entry", "reference_name": se_name,
                                 "child_row_reference": row.name, "item_code": row.item_code,
                                 "item_serial_no": (row.serial_no or "").strip() or None, "batch_no": row.batch_no,
                                 "sample_size": 1, "status": status, "manual_inspection": 1,
                                 "inspected_by": QC_USER, "report_date": frappe.utils.nowdate(),
                                 "remarks": "DEMO"}).insert()
            qi.submit()
            print(f"  QI {qi.name} {row.item_code} {row.serial_no or row.batch_no}: {status}, "
                  f"level={qi.satcom_inspection_level}, sample={qi.sample_size}")
    _as(APPROVER, lambda: _expect_block("non-QC user submits a Quality Inspection", lambda: frappe.get_doc({
        "doctype": "Quality Inspection", "inspection_type": "Outgoing", "reference_type": "Stock Entry",
        "reference_name": se_name, "item_code": rfc, "sample_size": 1, "status": "Accepted",
        "inspected_by": APPROVER, "manual_inspection": 1}).insert().submit()))
    _as(QC_USER, inspect)

    def wrong_target():
        doc = frappe.get_doc("Stock Entry", se_name)
        doc.items[1].t_warehouse = STORES_WH  # rejected serial to Stores
        doc.save()
        return doc.submit()
    _as(QC_USER, lambda: _expect_block("rejected row released to Stores", wrong_target))
    _as(QC_USER, lambda: _expect_block("QC release for a job that needs certificates, none attached",
                                       lambda: frappe.get_doc("Stock Entry", se_name).submit()))

    def attach_cert():
        pr = frappe.get_doc("Purchase Receipt", grn)
        f = _file("Purchase Receipt", grn, "DEMO-test-certificate.txt", "DEMO test certificate")
        for row in pr.items:
            if row.item_code == rfc:
                row.satcom_cert_attached = 1
                row.satcom_cert_file = f.file_url
        pr.save()
    _as(STORES, attach_cert)
    _as(QC_USER, lambda: frappe.get_doc("Stock Entry", se_name).submit())
    print(f"QC release {se_name} submitted by {QC_USER}: " + ", ".join(
        f"{n} -> {frappe.db.get_value('Serial No', n, 'warehouse')}" for n in s))

    # 5.3 dispositions (stores)
    def scrap(**over):
        return _transfer([(rfc, 1, s[1], None, REJECTED, over.pop("to", SCRAP_WH))], **over).insert().submit()
    _as(STORES, lambda: _expect_block("leaving Rejected without a disposition", lambda: scrap()))
    _as(STORES, lambda: _expect_block("scrap without a reason", lambda: scrap(satcom_disposition="Scrap")))
    _as(STORES, lambda: _expect_block("scrap sent to Stores", lambda: scrap(
        satcom_disposition="Scrap", satcom_disposition_reason="DEMO", to=STORES_WH)))
    _as(STORES, lambda: _expect_block("Return to Vendor as a stock entry", lambda: scrap(
        satcom_disposition="Return to Vendor", satcom_disposition_reason="DEMO")))
    _as(STORES, lambda: scrap(satcom_disposition="Scrap", satcom_disposition_reason="DEMO: connector pin bent"))
    print(f"scrap: {s[1]} -> {frappe.db.get_value('Serial No', s[1], 'warehouse')}")

    def concession(**over):
        return _transfer([(rfc, 1, s[2], None, REJECTED, STORES_WH)], satcom_disposition="Use under Concession",
                         satcom_disposition_reason="DEMO: cosmetic scratch, works", **over).insert().submit()
    _as(STORES, lambda: _expect_block("stores sets Concession Approved By to an approver",
                                      lambda: concession(satcom_concession_approved_by=APPROVER)))
    _as(STORES, concession)
    print(f"concession: {s[2]} -> {frappe.db.get_value('Serial No', s[2], 'warehouse')}")

    def vendor_return(reason):
        ret = make_return_doc("Purchase Receipt", grn)
        ret.items = [r for r in ret.items if r.item_code == rfc]
        r = ret.items[0]
        r.qty = r.received_qty = -1
        r.rejected_qty = 0
        r.warehouse = REJECTED
        r.use_serial_batch_fields = 1
        r.serial_no = s[3]
        r.serial_and_batch_bundle = None
        ret.satcom_disposition_reason = reason
        ret.insert()
        ret.submit()
        return ret
    _as(STORES, lambda: _expect_block("return to vendor without a reason", lambda: vendor_return("")))
    ret = _as(STORES, lambda: vendor_return("DEMO: wrong gain, supplier replaces"))
    print(f"return to vendor {ret.name} ({ret.satcom_disposition}): {s[3]} -> "
          f"{frappe.db.get_value('Serial No', s[3], 'warehouse') or 'gone (returned)'}")
    print(f"Pending QC after release: {len(frappe.db.sql(PENDING_QC_SQL))} line(s)")


def create_demo():
    """Build the DEMO records for what's been built so far (writes). Run cleanup() first to redo."""
    from frappe.model.workflow import apply_workflow

    if frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]}, limit=1):
        frappe.throw("DEMO jobs exist; run cleanup first")
    today = frappe.utils.nowdate()
    _snapshot_series()

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

    _demo_purchase_orders(made, codes, a)
    _demo_receipt_qc(made, codes)
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


LEDGER_TABLES = ["Stock Ledger Entry", "GL Entry", "Payment Ledger Entry", "Repost Item Valuation",
                 "Stock Reservation Entry"]


def _purge_voucher(voucher_type, voucher_no):
    """Remove a cancelled DEMO voucher's ledger rows and serial-and-batch bundles (demo data only:
    v16 keeps them as live links that block deleting the items, serials and batches). Returns the
    purged Stock Ledger Entry names (their counter is restored with the others)."""
    sles = frappe.get_all("Stock Ledger Entry", filters={"voucher_type": voucher_type, "voucher_no": voucher_no},
                          pluck="name")
    for dt in LEDGER_TABLES:
        frappe.db.delete(dt, {"voucher_type": voucher_type, "voucher_no": voucher_no})
    for b in frappe.get_all("Serial and Batch Bundle", filters={"voucher_type": voucher_type, "voucher_no": voucher_no},
                            pluck="name"):
        frappe.db.delete("Serial and Batch Entry", {"parent": b})
        frappe.db.delete("Serial and Batch Bundle", {"name": b})
    return sles


def _snapshot_series():
    import json
    if frappe.db.get_default(SERIES_KEY):
        frappe.throw("a DEMO counter snapshot exists; run cleanup first")
    frappe.db.set_default(SERIES_KEY, json.dumps(dict(frappe.db.sql("select name, current from tabSeries"))))


def _restore_counters(deleted):
    """Put the naming counters the demo used back to their value before create_demo (counters the
    demo made go). Only counters of records cleanup deleted ({doctype: [names]}) are touched, and
    never below a number still in use: other counters can move while the demo is on the site
    (ERPNext's nightly BOM Update Log did on 9 Nov), and lowering those would reuse a live name."""
    import json
    raw = frappe.db.get_default(SERIES_KEY)
    if not raw:
        return False
    before = json.loads(raw)
    demo_prefixes = {}
    for dt, names in deleted.items():
        for n in names:
            demo_prefixes[n.rstrip("0123456789")] = dt
    for name, current in frappe.db.sql("select name, current from tabSeries"):
        if name not in demo_prefixes:
            if current != before.get(name):
                print(f"counter {name}: {before.get(name)} -> {current} left alone (not a demo record's series)")
            continue
        in_use = frappe.db.sql(
            f"select max(cast(substring(name, %s) as unsigned)) from `tab{demo_prefixes[name]}`"
            " where name like %s and substring(name, %s) regexp '^[0-9]+$'",
            (len(name) + 1, name + "%", len(name) + 1))[0][0] or 0
        target = max(before.get(name) or 0, in_use)
        if name not in before and not in_use:
            frappe.db.sql("delete from tabSeries where name=%s", name)
            print(f"counter {name}: {current} -> removed (made by the demo)")
        elif current != target:
            frappe.db.sql("update tabSeries set current=%s where name=%s", (target, name))
            print(f"counter {name}: {current} -> {target}")
    frappe.db.set_default(SERIES_KEY, "")
    return True


def cleanup():
    """Remove DEMO test records (writes): GRNs, returns, QC releases, dispositions and inspections of
    DEMO items (cancelled, then their ledger rows purged), DEMO purchase orders and supplier quotations,
    DEMO indents, items (with their serials and batches), jobs, the DEMO customer and suppliers, with
    notifications, files and Deleted Document rows. Counters go back to their values before create_demo."""
    demo_items = sorted({i.name for i in frappe.get_all("Item", filters={"item_name": ["like", "DEMO%"]}, fields=["name"])}
                        | {i.name for i in frappe.get_all("Item", filters={"satcom_mpn": ["like", "DEMO%"]}, fields=["name"])})
    demo_jobs = frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]}, pluck="name")
    deleted = {}

    def parents(child_dt, field="item_code"):
        if not demo_items:
            return []
        return sorted(set(frappe.get_all(child_dt, filters={field: ["in", demo_items]}, pluck="parent")), reverse=True)

    reposts_before = set(frappe.get_all("Repost Item Valuation", pluck="name"))
    purged_sles = []
    # stock documents, newest first: returns and dispositions before the QC release, inspections,
    # then the receipts
    stock = [("Stock Entry", n) for n in parents("Stock Entry Detail")]
    receipts = parents("Purchase Receipt Item")
    returns = [n for n in receipts if frappe.db.get_value("Purchase Receipt", n, "is_return")]
    stock = [("Purchase Receipt", n) for n in returns] + stock
    inspections = frappe.get_all("Quality Inspection", filters={"item_code": ["in", demo_items or [""]]}, pluck="name")
    stock += [("Quality Inspection", n) for n in inspections]
    stock += [("Purchase Receipt", n) for n in receipts if n not in returns]
    for dt, name in stock:
        doc = frappe.get_doc(dt, name)
        if doc.docstatus == 1:
            doc.flags.ignore_links = True
            doc.ignore_linked_doctypes = ("Quality Inspection", "Serial and Batch Bundle", "Stock Ledger Entry",
                                          "Repost Item Valuation", "Purchase Receipt", "Stock Entry")
            doc.cancel()
    for dt, name in stock:
        if dt != "Quality Inspection":
            purged_sles.extend(_purge_voucher(dt, name))
        frappe.db.delete("File", {"attached_to_doctype": dt, "attached_to_name": name})
        frappe.delete_doc(dt, name, force=1)
        deleted.setdefault(dt, []).append(name)
        print(f"deleted {dt} {name}")
    new_reposts = [r for r in frappe.get_all("Repost Item Valuation", fields=["name", "item_code"])
                   if r.name not in reposts_before and r.item_code in demo_items]
    if new_reposts:
        frappe.db.delete("Repost Item Valuation", {"name": ["in", [r.name for r in new_reposts]]})
        print(f"purged {len(new_reposts)} Repost Item Valuation row(s) queued by the cancels")

    # purchase orders (cancelled first when approved), then the supplier quotations they compare
    for dt, child in (("Purchase Order", "Purchase Order Item"), ("Supplier Quotation", "Supplier Quotation Item")):
        names = set(parents(child)) | set(frappe.get_all(dt, filters={"supplier": ["in", DEMO_SUPPLIERS]}, pluck="name"))
        for d in frappe.get_all(dt, filters={"name": ["in", list(names) or [""]]}, fields=["name", "docstatus"],
                                order_by="name desc"):
            if d.docstatus == 1:
                frappe.get_doc(dt, d.name).cancel()
            for log_dt, field in (("Workflow Action", "reference_name"), ("Notification Log", "document_name")):
                frappe.db.delete(log_dt, {field: d.name})
            frappe.delete_doc(dt, d.name, force=1)
            deleted.setdefault(dt, []).append(d.name)
            print(f"deleted {dt} {d.name}")

    # indents
    names = set(frappe.get_all("Material Request", filters={"title": ["like", "DEMO%"]}, pluck="name"))
    if demo_jobs:
        names |= set(frappe.get_all("Material Request", filters={"satcom_job": ["in", demo_jobs]}, pluck="name"))
    names |= set(parents("Material Request Item"))
    for mr in frappe.get_all("Material Request", filters={"name": ["in", list(names) or [""]]},
                             fields=["name", "docstatus"], order_by="name desc"):
        if mr.docstatus == 1:
            frappe.db.set_value("Material Request", mr.name, "satcom_cancel_reason", "DEMO cleanup")
            frappe.get_doc("Material Request", mr.name).cancel()
        for dt, field in (("Workflow Action", "reference_name"), ("Notification Log", "document_name")):
            frappe.db.delete(dt, {field: mr.name})
        frappe.delete_doc("Material Request", mr.name)
        deleted.setdefault("Material Request", []).append(mr.name)
        print(f"deleted Material Request {mr.name}")

    # serials, batches, items
    for dt, field in (("Serial No", "item_code"), ("Batch", "item")):
        for name in frappe.get_all(dt, filters={field: ["in", demo_items or [""]]}, pluck="name"):
            frappe.delete_doc(dt, name, force=1)
            deleted.setdefault(dt, []).append(name)
        if deleted.get(dt):
            print(f"deleted {len(deleted[dt])} {dt}")
    for name in demo_items:
        frappe.delete_doc("Item", name)
        deleted.setdefault("Item", []).append(name)
        print(f"deleted Item {name}")

    jobs = frappe.get_all("Project", filters={"satcom_job_title": ["like", "DEMO%"]},
                          fields=["name", "satcom_job_type"], order_by="name desc")
    jobs.sort(key=lambda j: j.satcom_job_type != "Extension")  # extensions before their parents
    for j in jobs:
        frappe.delete_doc("Project", j.name)
        deleted.setdefault("Project", []).append(j.name)
        print(f"deleted Project {j.name}")
    for dt, name in (("Customer", DEMO_CUSTOMER), *(("Supplier", s) for s in DEMO_SUPPLIERS)):
        if frappe.db.exists(dt, name):
            frappe.delete_doc(dt, name)
            deleted.setdefault(dt, []).append(name)
            print(f"deleted {dt} {name}")
    for dt, names in deleted.items():
        frappe.db.delete("Deleted Document", {"deleted_doctype": dt, "deleted_name": ["in", names]})
    if not _restore_counters({**deleted, "Stock Ledger Entry": purged_sles}):  # else: demo predates the snapshot
        yy = frappe.utils.nowdate()[2:4]
        _restore_series([f"J-{yy}-", f"S-{yy}-"] + [j.name + "-" for j in jobs])
        _restore_series([f"MAT-MR-{frappe.utils.nowdate()[:4]}-"], table="tabMaterial Request")
    frappe.db.commit()
    print("cleanup: " + ", ".join(f"{len(v)} {k}" for k, v in deleted.items()))


def _section_5_receipt_qc():
    from erpnext.satcom_p1_receipt_qc import DISPOSITIONS, PENDING_QC_REPORT, QC_RELEASE_TYPE, QI_PARAMETERS, QI_TEMPLATE

    pr = frappe.get_meta("Purchase Receipt")
    _check("5.1 GRN vendor invoice / DC fields",
           all(pr.has_field(fn) for fn in ("satcom_vendor_invoice_no", "satcom_vendor_invoice_date",
                                           "satcom_vendor_dc_no", "satcom_vendor_dc_date")))
    pri = frappe.get_meta("Purchase Receipt Item")
    _check("5.1 GRN row certificate fields (editable after submit)",
           pri.has_field("satcom_cert_attached") and pri.get_field("satcom_cert_file").allow_on_submit)
    _check("5.1 Serial No and Batch record the job received for",
           frappe.get_meta("Serial No").has_field("satcom_received_for_job")
           and frappe.get_meta("Batch").has_field("satcom_received_for_job"))
    for name, dt, event in (("Satcom GRN - rules", "Purchase Receipt", "Before Save"),
                            ("Satcom GRN - submit guard", "Purchase Receipt", "Before Submit"),
                            ("Satcom GRN - job on serials and batches", "Purchase Receipt", "After Submit"),
                            ("Satcom Quality Inspection - level", "Quality Inspection", "Before Save"),
                            ("Satcom Serial No - job from GRN", "Serial No", "Before Save"),
                            ("Satcom Batch - job from GRN", "Batch", "Before Save"),
                            ("Satcom Stock Entry - rules", "Stock Entry", "Before Save"),
                            ("Satcom QC release - rules", "Stock Entry", "Before Submit")):
        sc = frappe.db.get_value("Server Script", name, ["disabled", "doctype_event", "reference_doctype"], as_dict=True)
        _check(f"5 server script {name}", sc and not sc.disabled and sc.doctype_event == event
               and sc.reference_doctype == dt, sc)
    ss = frappe.get_single("Stock Settings")
    _check("5.2 QI rejected action Warn, not submitted Stop",
           ss.action_if_quality_inspection_is_rejected == "Warn"
           and ss.action_if_quality_inspection_is_not_submitted == "Stop")
    params = frappe.get_all("Item Quality Inspection Parameter", filters={"parent": QI_TEMPLATE}, pluck="specification")
    _check(f"5.2 template {QI_TEMPLATE} has the starter checks", set(QI_PARAMETERS) <= set(params), params)
    groups = frappe.get_all("Item Group", filters={"satcom_prefix": ["is", "set"]}, pluck="name")
    missing = frappe.get_all("Item", filters={"item_group": ["in", groups], "quality_inspection_template": ["is", "not set"]},
                             pluck="name")
    _check(f"5.2 every Satcom item has a QI template", not missing, missing)
    for user, can in ((QC_USER, True), (STORES, True), (APPROVER, False), (INDENTER, False)):
        has = bool(frappe.has_permission("Quality Inspection", "submit", user=user))
        _check(f"5.2 {user} {'can' if can else 'cannot'} submit Quality Inspections", has == can, has)
    _check(f"5.2 Stock Entry Type {QC_RELEASE_TYPE}",
           frappe.db.get_value("Stock Entry Type", QC_RELEASE_TYPE, "purpose") == "Material Transfer")
    _check(f"5.2 report {PENDING_QC_REPORT}", frappe.db.get_value("Report", PENDING_QC_REPORT, "report_type") == "Query Report")
    opts = (frappe.get_meta("Stock Entry").get_field("satcom_disposition").options or "").split("\n")[1:]
    _check("5.3 Stock Entry disposition options", opts == DISPOSITIONS, opts)

    grns = frappe.get_all("Purchase Receipt", filters={"supplier": DEMO_SUPPLIER, "is_return": 0, "docstatus": 1},
                          pluck="name")
    if grns:
        rfc = frappe.db.get_value("Item", {"item_name": "DEMO RF amplifier"}, "name")
        sn = frappe.get_all("Serial No", filters={"item_code": rfc}, fields=["name", "warehouse", "satcom_received_for_job"],
                            order_by="name")
        _check("5 demo serials: accepted -> Stores, scrapped -> Scrap, concession -> Stores, returned -> gone",
               [x.warehouse for x in sn] == [STORES_WH, SCRAP_WH, STORES_WH, None], [(x.name, x.warehouse) for x in sn])
        _check("5 demo serials record the job they were received for",
               {x.satcom_received_for_job for x in sn} == {DEMO_JOBS and frappe.db.get_value(
                   "Project", {"satcom_job_title": DEMO_JOBS[0][0]}, "name")})
        con = frappe.db.get_value("Item", {"item_name": "DEMO SMA connector"}, "name")
        b = frappe.get_all("Batch", filters={"item": con}, fields=["name", "satcom_received_for_job"])
        _check("5 demo batch records its stock build job", b and b[0].satcom_received_for_job == frappe.db.get_value(
            "Project", {"satcom_job_title": DEMO_JOBS[1][0]}, "name"), b)
        qis = frappe.get_all("Quality Inspection", filters={"item_code": ["in", [rfc, con]], "docstatus": 1},
                             fields=["status", "satcom_inspection_level", "item_code"])
        _check("5 demo inspections: 2 accepted, 3 rejected; job level 100% on the RF part, Standard on the stock build",
               sorted(q.status for q in qis) == ["Accepted", "Accepted", "Rejected", "Rejected", "Rejected"]
               and {q.satcom_inspection_level for q in qis if q.item_code == rfc} == {"100% inspection"}
               and {q.satcom_inspection_level for q in qis if q.item_code == con} == {"Standard checks"}, qis)
        rets = frappe.get_all("Purchase Receipt", filters={"supplier": DEMO_SUPPLIER, "is_return": 1, "docstatus": 1},
                              fields=["satcom_disposition", "satcom_disposition_reason"])
        _check("5.3 demo return to vendor records disposition and reason",
               rets and rets[0].satcom_disposition == "Return to Vendor" and rets[0].satcom_disposition_reason, rets)
        disp = frappe.get_all("Stock Entry", filters={"satcom_disposition": ["in", ["Scrap", "Use under Concession"]],
                                                     "docstatus": 1}, fields=["satcom_disposition", "satcom_disposition_reason"])
        _check("5.3 demo scrap and concession entries with reasons",
               sorted(d.satcom_disposition for d in disp) == ["Scrap", "Use under Concession"]
               and all(d.satcom_disposition_reason for d in disp), disp)
        from erpnext.satcom_p1_receipt_qc import PENDING_QC_SQL
        _check("5.2 Pending QC empty after the release", not frappe.db.sql(PENDING_QC_SQL))


def _section_4_purchase_orders():
    from erpnext import satcom_p1_purchase_orders as p4

    # 4.1 Satcom Settings: OPEN items are settings with the spec's default; a changed value is not a failure
    dt = frappe.db.get_value("DocType", p4.SETTINGS, ["issingle", "custom"], as_dict=True)
    _check(f"4.1 single DocType {p4.SETTINGS}", dt and dt.issingle and dt.custom, dt)
    if dt:
        meta = frappe.get_meta(p4.SETTINGS)
        stored = frappe.db.get_singles_dict(p4.SETTINGS)
        for field, default in p4.SETTINGS_DEFAULTS.items():
            df = meta.get_field(field)
            _check(f"4.1 {p4.SETTINGS}.{field}: spec default {default!r}, now {stored.get(field)!r}",
                   df and str(df.default or 0) == str(default) and field in stored, (df and df.default, stored.get(field)))
        _check("4.1 threshold basis options", (meta.get_field("threshold_basis").options or "").split("\n")
               == p4.THRESHOLD_BASES)
    # 4.1 quotations on the PO, waiver
    child = frappe.db.get_value("DocType", p4.PO_QUOTATION, ["istable", "custom"], as_dict=True)
    _check(f"4.1 child table {p4.PO_QUOTATION}", child and child.istable and child.custom, child)
    if child:
        cm = frappe.get_meta(p4.PO_QUOTATION)
        sq, sup = cm.get_field("supplier_quotation"), cm.get_field("supplier")
        _check("4.1 quotation row links a Supplier Quotation; supplier filled automatically",
               sq and sq.options == "Supplier Quotation" and sq.reqd and sup and sup.read_only
               and sup.fetch_from == "supplier_quotation.supplier")
    po = frappe.get_meta("Purchase Order")
    q = po.get_field("satcom_quotations")
    _check("4.1 Purchase Order table satcom_quotations", q and q.fieldtype == "Table" and q.options == p4.PO_QUOTATION)
    _check("4.1 waiver fields (not copied to a new PO; reason required when waived)",
           po.has_field("satcom_quote_waived") and po.has_field("satcom_waiver_reason")
           and po.get_field("satcom_quote_waived").no_copy and po.get_field("satcom_waiver_reason").no_copy
           and po.get_field("satcom_waiver_reason").mandatory_depends_on)
    # 4.2 approval
    _check("4.2 Purchase Order field satcom_rejection_reason", po.has_field("satcom_rejection_reason"))
    for name, event in (("Satcom PO - rules", "Before Save"), ("Satcom PO - approval guard", "Before Submit"),
                        ("Satcom PO - quotation rule", "Before Submit")):
        sc = frappe.db.get_value("Server Script", name, ["disabled", "doctype_event", "reference_doctype"], as_dict=True)
        _check(f"4 server script {name}", sc and not sc.disabled and sc.doctype_event == event
               and sc.reference_doctype == "Purchase Order", sc)
    _check("4 client script Satcom PO (reject reason dialog)", frappe.db.get_value("Client Script", "Satcom PO", "enabled"))
    wf = frappe.get_doc("Workflow", p4.PO_WORKFLOW) if frappe.db.exists("Workflow", p4.PO_WORKFLOW) else None
    _check(f"4.2 workflow {p4.PO_WORKFLOW} active on Purchase Order, no email",
           wf and wf.is_active and wf.document_type == "Purchase Order" and not wf.send_email_alert)
    if wf:
        _check("4.2 workflow states", [(s.state, s.doc_status, s.allow_edit) for s in wf.states]
               == [(s, d, r) for s, (d, r, _) in p4.PO_STATES.items()])
        _check("4.2 workflow transitions (Approve: no self approval)",
               [(t.state, t.action, t.next_state, t.allowed, t.allow_self_approval) for t in wf.transitions]
               == [tuple(t) for t in p4.PO_TRANSITIONS])
    for user, can in ((INDENTER, True), (ALL_ROLES, True), (STORES, False)):
        has = bool(frappe.has_permission("Purchase Order", "create", user=user))
        _check(f"4.2 {user} {'can' if can else 'cannot'} raise purchase orders", has == can, has)
    # 4.2 letterhead, company details, addresses, print format
    lh = frappe.db.get_value("Letter Head", p4.LETTERHEAD, ["is_default", "disabled", "content"], as_dict=True)
    _check(f"4.2 letterhead {p4.LETTERHEAD} is the default", lh and lh.is_default and not lh.disabled)
    _check("4.2 it is the only default letterhead", frappe.db.count("Letter Head", {"is_default": 1}) == 1)
    if lh:
        text = lh.content or ""
        missing = [x for x in (p4.REGISTERED_OFFICE, p4.FACTORY, p4.CIN, p4.GSTIN, p4.PHONE, p4.FAX, p4.EMAIL,
                               p4.WEBSITE, "<img") if x not in text]
        _check("4.2 letterhead shows the logo, registered office, factory, CIN and GSTIN", not missing, missing)
    co = frappe.db.get_value("Company", COMPANY, ["tax_id", "default_letter_head"], as_dict=True)
    cin = frappe.db.get_value("Company", COMPANY, "satcom_cin") if frappe.get_meta("Company").has_field("satcom_cin") else None
    _check("4.2 Company GSTIN (Tax ID), CIN and default letterhead",
           co.tax_id == p4.GSTIN and cin == p4.CIN and co.default_letter_head == p4.LETTERHEAD, (co, cin))
    for title, values in p4.ADDRESSES.items():
        a = frappe.db.get_value("Address", {"address_title": title, "address_type": values["address_type"]},
                                ["name", "address_line1", "city", "pincode", "is_primary_address",
                                 "is_shipping_address", "disabled"], as_dict=True)
        linked = a and frappe.db.exists("Dynamic Link", {"parenttype": "Address", "parent": a.name,
                                                         "link_doctype": "Company", "link_name": COMPANY})
        _check(f"4.2 address {title} ({values['address_type']}) linked to the company",
               a and linked and not a.disabled and a.address_line1 == values["address_line1"]
               and a.pincode == values["pincode"] and a.is_primary_address == values["is_primary_address"]
               and a.is_shipping_address == values["is_shipping_address"], a)
    pf = frappe.db.get_value("Print Format", p4.PO_FORMAT, ["doc_type", "custom_format", "print_format_type",
                                                             "disabled", "html"], as_dict=True)
    _check(f"4.2 print format {p4.PO_FORMAT} on Purchase Order (job on each row, delivery address)",
           pf and pf.doc_type == "Purchase Order" and pf.custom_format and pf.print_format_type == "Jinja"
           and not pf.disabled and "row.project" in (pf.html or "") and "shipping_address_display" in (pf.html or ""))
    _check(f"4.2 {p4.PO_FORMAT} is the Purchase Order's default print format",
           po.default_print_format == p4.PO_FORMAT, po.default_print_format)
    # 5.1 once section 4 is live
    _check("4 / 5.1 a GRN needs a purchase order (Purchase Order Required = Yes)",
           frappe.db.get_single_value("Buying Settings", "po_required") == "Yes")

    demo = {d.get(PO_LABEL): d for d in frappe.get_all(
        "Purchase Order", filters={PO_LABEL: ["like", "DEMO-%"]},
        fields=["name", PO_LABEL, "workflow_state", "docstatus", "base_net_total", "satcom_quote_waived",
                "satcom_waiver_reason", "satcom_rejection_reason", "shipping_address", "owner"])}
    if demo:
        def state(label, workflow_state, docstatus):
            d = demo.get(label)
            return d and d.workflow_state == workflow_state and d.docstatus == docstatus

        def projects(label):
            return frappe.get_all("Purchase Order Item", filters={"parent": demo[label].name}, pluck="project")

        a = demo.get("DEMO-4L-2Q")
        _check("4.1 demo Rs 4,00,000 PO with 2 quotations: not approved, rejected with a reason",
               state("DEMO-4L-2Q", "Rejected", 0) and a.base_net_total == 400000 and a.satcom_rejection_reason, a)
        _check("4.1 demo Rs 4,00,000 PO with 2 suppliers quoting (one twice, one draft) stays pending",
               state("DEMO-4L-SAME", "Pending Approval", 0), demo.get("DEMO-4L-SAME"))
        _check("4.1 demo Rs 4,00,000 PO with 3 suppliers quoting is approved",
               state("DEMO-4L-3Q", "Approved", 1), demo.get("DEMO-4L-3Q"))
        d = demo.get("DEMO-4L-WAIVED")
        _check("4.1 demo Rs 4,00,000 PO with 1 quotation, waived by an approver with a reason, is approved",
               state("DEMO-4L-WAIVED", "Approved", 1) and d.satcom_quote_waived and d.satcom_waiver_reason, d)
        _check("4.1 / 4.2 demo Rs 50,000 tools PO: no quotations, no job, approved",
               state("DEMO-50K-TOOLS", "Approved", 1) and not any(projects("DEMO-50K-TOOLS")), demo.get("DEMO-50K-TOOLS"))
        _check("4.2 demo self-approval stays pending", state("DEMO-SELF", "Pending Approval", 0), demo.get("DEMO-SELF"))
        g = demo.get("DEMO-FROM-INDENT")
        job = frappe.db.get_value("Project", {"satcom_job_title": DEMO_JOBS[0][0]}, "name")
        _check("4.2 demo PO made from the approved indent carries the indent's job on its rows",
               state("DEMO-FROM-INDENT", "Approved", 1) and set(projects("DEMO-FROM-INDENT")) == {job}, g)
        factory = frappe.db.get_value("Address", {"address_title": p4.FACTORY_TITLE, "address_type": "Shipping"}, "name")
        _check("4.2 demo POs deliver to the factory",
               factory and {x.shipping_address for x in demo.values()} == {factory},
               sorted({str(x.shipping_address) for x in demo.values()}))
        r = demo.get("DEMO-GRN")
        grn_pos = set(frappe.get_all("Purchase Receipt Item", filters={"parenttype": "Purchase Receipt", "docstatus": 1,
                                                                     "purchase_order": r.name if r else ""},
                                     pluck="parent"))
        _check("4 / 5.1 demo GRN was made from an approved PO", state("DEMO-GRN", "Approved", 1) and grn_pos, r)


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
    _section_4_purchase_orders()
    _section_5_receipt_qc()
    failed = _results.count(False)
    print(f"{len(_results) - failed}/{len(_results)} PASS" + (f", {failed} FAIL" if failed else ""))
