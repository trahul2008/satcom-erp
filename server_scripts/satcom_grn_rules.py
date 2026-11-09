# Satcom GRN - rules  (Server Script: DocType Event, Purchase Receipt, Before Save)
# SPEC_PHASE1 5.1 / 5.3. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
# Receipts: everything goes to Quality Hold (QC releases it), each row names its job (tools may go
# without, as on indents). Returns from Rejected are the "Return to Vendor" disposition: reason needed.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

QH = "Quality Hold - STPL"
REJECTED = "Rejected - STPL"
problems = []

if not doc.is_return:
    tool_groups = frappe.get_all("Item Group", filters={"satcom_prefix": "TOL"}, pluck="name")
    doc.set_warehouse = QH
    for row in doc.items:
        if not row.warehouse:
            row.warehouse = QH
        if row.warehouse != QH:
            problems.append("Row " + str(row.idx) + ": everything received goes to " + QH
                            + " first; QC releases it to Stores.")
        group = row.item_group or frappe.db.get_value("Item", row.item_code, "item_group")
        if not row.project and group not in tool_groups:
            problems.append("Row " + str(row.idx) + " (" + row.item_code + "): pick the Job this material was received for."
                            + " Only tools (TOL) may go without a job.")
else:
    from_rejected = False
    for row in doc.items:
        if row.warehouse == REJECTED:
            from_rejected = True
    if from_rejected:
        doc.satcom_disposition = "Return to Vendor"
        if not (doc.satcom_disposition_reason or "").strip():
            problems.append("Returning rejected material to the vendor: enter the Disposition Reason (why it goes back).")

if problems:
    frappe.throw("<br>".join(problems), title="GRN rules")
