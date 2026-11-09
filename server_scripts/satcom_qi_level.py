# Satcom Quality Inspection - level  (Server Script: DocType Event, Quality Inspection, Before Save)
# SPEC_PHASE1 5.2. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
# Shows the inspection level the job asks for (satcom_incoming_inspection): no job or a stock build
# means Standard checks. "100% inspection" sets the sample size to the row's full quantity.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

if doc.reference_type == "Stock Entry" and doc.reference_name:
    row = None
    if doc.child_row_reference:
        row = frappe.db.get_value("Stock Entry Detail", doc.child_row_reference, ["project", "transfer_qty", "qty"],
                                  as_dict=True)
    if not row:
        rows = frappe.db.sql("select project, transfer_qty, qty from `tabStock Entry Detail`"
                             " where parent = %s and item_code = %s limit 1", (doc.reference_name, doc.item_code), as_dict=True)
        row = rows[0] if rows else None
    level = "Standard checks"
    job = row.project if row else None
    if job:
        j = frappe.db.get_value("Project", job, ["satcom_job_type", "satcom_incoming_inspection"], as_dict=True)
        if j and j.satcom_job_type != "Stock Build" and j.satcom_incoming_inspection:
            level = j.satcom_incoming_inspection
    doc.satcom_job = job
    doc.satcom_inspection_level = level
    if level == "100% inspection" and row:
        doc.sample_size = row.transfer_qty or row.qty
