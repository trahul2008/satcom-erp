# Satcom PO - rules  (Server Script: DocType Event, Purchase Order, Before Save)
# SPEC_PHASE1 4.1 / 4.2. Source of truth is this file; satcom_p1_purchase_orders.py writes it into ERPNext.
#  - Job: every row except tools (TOL) needs one. A row made from an indent arrives with the indent
#    row's job (ERPNext copies it, and itself blocks a PO row whose job differs from its indent row).
#  - Quotations table: each row's Supplier is the quotation's supplier.
#  - Waiver of the quotation rule: only a Satcom Approver sets it, and it needs a reason.
#  - A rejection needs its reason.
#  - Delivery address: the factory, when none is picked.
# The quotation rule itself is checked when the PO is approved (Satcom PO - quotation rule).
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

FACTORY_TITLE = "Satcom Technologies Factory"
problems = []
user = frappe.session.user

# 4.2 job per row
tool_groups = frappe.get_all("Item Group", filters={"satcom_prefix": "TOL"}, pluck="name")
for row in doc.items:
    group = row.item_group or frappe.db.get_value("Item", row.item_code, "item_group")
    if not row.project and group not in tool_groups:
        problems.append("Row " + str(row.idx) + " (" + str(row.item_code) + "): pick the Job this material is ordered for."
                        + " Only tools (TOL) may go without a job.")

# 4.1 supplier of each linked quotation
for q in doc.satcom_quotations:
    if q.supplier_quotation:
        q.supplier = frappe.db.get_value("Supplier Quotation", q.supplier_quotation, "supplier")

# 4.1 waiver: approvers only, with a reason
if doc.satcom_quote_waived:
    reason = (doc.satcom_waiver_reason or "").strip()
    if not reason:
        problems.append("Enter the Waiver Reason: why this PO goes ahead without the quotations.")
    waived_before = 0
    reason_before = ""
    if not doc.flags.in_insert:
        saved = frappe.db.get_value("Purchase Order", doc.name, ["satcom_quote_waived", "satcom_waiver_reason"],
                                    as_dict=True)
        if saved:
            waived_before = saved.satcom_quote_waived
            reason_before = (saved.satcom_waiver_reason or "").strip()
    if not waived_before or reason != reason_before:
        is_approver = frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": "Satcom Approver"})
        if user != "Administrator" and not is_approver:
            problems.append("Only a Satcom Approver can waive the quotation rule or change the Waiver Reason.")

# 4.2 rejection
if doc.workflow_state == "Rejected" and not (doc.satcom_rejection_reason or "").strip():
    problems.append("Enter the Rejection Reason before rejecting.")

# 4.2 delivery address = the factory, unless another one was picked
if not doc.shipping_address:
    factory = frappe.db.get_value("Address", {"address_title": FACTORY_TITLE, "address_type": "Shipping",
                                              "disabled": 0}, "name")
    if factory:
        a = frappe.db.get_value("Address", factory, ["address_line1", "address_line2", "city", "county", "state",
                                                     "pincode", "country"], as_dict=True)
        lines = []
        for part in [a.address_line1, a.address_line2, a.city, a.county]:
            if part:
                lines.append(part)
        lines.append(((a.state or "") + " " + (a.pincode or "")).strip())
        if a.country:
            lines.append(a.country)
        doc.shipping_address = factory
        doc.shipping_address_display = "<br>".join(lines)

if problems:
    frappe.throw("<br>".join(problems), title="Purchase order rules")
