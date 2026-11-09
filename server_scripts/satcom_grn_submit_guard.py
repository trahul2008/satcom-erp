# Satcom GRN - submit guard  (Server Script: DocType Event, Purchase Receipt, Before Submit)
# SPEC_PHASE1 5.1. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
# A receipt needs the vendor's invoice and DC numbers and dates, and at least one attachment
# (the invoice / DC scan). Returns are exempt.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

if not doc.is_return:
    problems = []
    if not (doc.satcom_vendor_invoice_no or "").strip() or not doc.satcom_vendor_invoice_date:
        problems.append("Enter the Vendor Invoice No and Date.")
    if not (doc.satcom_vendor_dc_no or "").strip() or not doc.satcom_vendor_dc_date:
        problems.append("Enter the Vendor DC No and Date.")
    if not frappe.db.count("File", {"attached_to_doctype": "Purchase Receipt", "attached_to_name": doc.name}):
        problems.append("Attach the invoice / DC scan (paperclip in the sidebar) before submitting.")
    if problems:
        frappe.throw("<br>".join(problems), title="GRN rules")
