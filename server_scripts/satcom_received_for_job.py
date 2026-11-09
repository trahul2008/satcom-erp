# Satcom serial / batch - job from GRN  (Server Script: DocType Event, Serial No and Batch, Before Save)
# SPEC_PHASE1 5.1. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext
# (one Server Script per doctype, same source).
# A serial or batch made by a GRN records the job of that GRN row. ERPNext creates them during the
# GRN's submit, before its After Submit scripts can read the bundle, so the record looks itself up.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

item = doc.get("item_code") or doc.get("item")
if not doc.satcom_received_for_job and doc.reference_doctype == "Purchase Receipt" and doc.reference_name and item:
    rows = frappe.db.sql("select project from `tabPurchase Receipt Item` where parent = %s and item_code = %s"
                         " and ifnull(project, '') != '' order by idx limit 1", (doc.reference_name, item), as_dict=True)
    if rows:
        doc.satcom_received_for_job = rows[0].project
