# Satcom GRN - job on serials and batches  (Server Script: DocType Event, Purchase Receipt, After Submit)
# SPEC_PHASE1 5.1. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
# Each Serial No and Batch received records the job it was received for (satcom_received_for_job),
# from the GRN row's job. Used by QC release (inspection level, certificates) and issues (7).
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

if not doc.is_return:
    for row in doc.items:
        if not row.project:
            continue
        # ERPNext links the row to its bundle with a direct DB write during submit, so the row in
        # memory doesn't have it yet, and it bulk-inserts serial numbers (no Serial No hooks run):
        # read the bundle's entries from the database by voucher and row.
        entries = frappe.db.sql(
            """select e.serial_no, e.batch_no
                 from `tabSerial and Batch Entry` e
                 join `tabSerial and Batch Bundle` b on b.name = e.parent
                where b.voucher_type = 'Purchase Receipt' and b.voucher_no = %s and b.voucher_detail_no = %s
                  and b.docstatus = 1""", (doc.name, row.name), as_dict=True)
        if entries:
            for e in entries:
                if e.serial_no:
                    frappe.db.set_value("Serial No", e.serial_no, "satcom_received_for_job", row.project)
                if e.batch_no:
                    frappe.db.set_value("Batch", e.batch_no, "satcom_received_for_job", row.project)
        for s in (row.serial_no or "").split("\n"):
            if s.strip():
                frappe.db.set_value("Serial No", s.strip(), "satcom_received_for_job", row.project)
        if row.batch_no:
            frappe.db.set_value("Batch", row.batch_no, "satcom_received_for_job", row.project)
