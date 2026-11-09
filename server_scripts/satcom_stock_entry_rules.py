# Satcom Stock Entry - rules  (Server Script: DocType Event, Stock Entry, Before Save)
# SPEC_PHASE1 5.2 / 5.3. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
#  - Moving stock out of Quality Hold is a QC release: Inspection Required goes on, and each row
#    carries the job its serial / batch was received for.
#  - Moving stock out of Rejected needs a Disposition and its reason: Scrap goes to Scrap - STPL (or
#    a Material Issue), Use under Concession goes to Stores; Return to Vendor is a Purchase Return.
#    Concession approval by a Satcom Approver when Satcom Settings asks for it (spec default: off).
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

QH = "Quality Hold - STPL"
REJECTED = "Rejected - STPL"
STORES = "Stores - STPL"
SCRAP = "Scrap - STPL"
problems = []


def received_for_job(row):
    serial = ""
    for s in (row.serial_no or "").split("\n"):
        if s.strip() and not serial:
            serial = s.strip()
    batch = row.batch_no
    if not serial and not batch and row.serial_and_batch_bundle:
        e = frappe.db.sql("select serial_no, batch_no from `tabSerial and Batch Entry` where parent = %s limit 1",
                          (row.serial_and_batch_bundle,), as_dict=True)
        if e:
            serial = e[0].serial_no
            batch = e[0].batch_no
    if serial:
        return frappe.db.get_value("Serial No", serial, "satcom_received_for_job")
    if batch:
        return frappe.db.get_value("Batch", batch, "satcom_received_for_job")
    return None


from_qh = False
from_rejected = False
for row in doc.items:
    if row.s_warehouse == QH:
        from_qh = True
        if not row.project:
            row.project = received_for_job(row)
    if row.s_warehouse == REJECTED:
        from_rejected = True

if from_qh:
    doc.inspection_required = 1

if from_rejected:
    disp = doc.satcom_disposition
    if not disp:
        problems.append("Stock leaving " + REJECTED + " needs a Disposition: Scrap or Use under Concession"
                        + " (Return to Vendor is a Purchase Return against the GRN).")
    elif disp == "Return to Vendor":
        problems.append("Return to Vendor is a Purchase Return: open the GRN, Create > Return, and take the rows from " + REJECTED + ".")
    if not (doc.satcom_disposition_reason or "").strip():
        problems.append("Enter the Disposition Reason: who decided and why is kept with the entry.")
    for row in doc.items:
        if row.s_warehouse != REJECTED:
            continue
        if disp == "Scrap" and row.t_warehouse != SCRAP and not (doc.purpose == "Material Issue" and not row.t_warehouse):
            problems.append("Row " + str(row.idx) + ": scrapped material goes to " + SCRAP + " (or use a Material Issue).")
        if disp == "Use under Concession" and row.t_warehouse != STORES:
            problems.append("Row " + str(row.idx) + ": material used under concession goes to " + STORES + ".")
    if disp == "Use under Concession":
        needs_approver = 0
        if frappe.db.exists("DocType", "Satcom Settings"):
            needs_approver = frappe.db.get_single_value("Satcom Settings", "concession_needs_approver")
        if needs_approver and not doc.satcom_concession_approved_by:
            problems.append("Concessions need a Satcom Approver: the approver sets Concession Approved By.")

approved_by = doc.satcom_concession_approved_by
if approved_by:
    before = None
    if not doc.flags.in_insert:
        before = frappe.db.get_value("Stock Entry", doc.name, "satcom_concession_approved_by")
    if approved_by != before:
        is_approver = frappe.db.exists("Has Role", {"parenttype": "User", "parent": approved_by, "role": "Satcom Approver"})
        if approved_by != frappe.session.user or not is_approver:
            problems.append("Concession Approved By can only be set by that Satcom Approver, signed in as themselves.")

if problems:
    frappe.throw("<br>".join(problems), title="Stock movement rules")
