# Satcom QC release - rules  (Server Script: DocType Event, Stock Entry, Before Submit)
# SPEC_PHASE1 5.2. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
# Stock Settings "Action if Quality Inspection is rejected" is Warn, so the real rule lives here,
# for rows leaving Quality Hold: a Rejected inspection may only go to Rejected - STPL, and a row
# going to Stores needs an Accepted inspection. If the row's job needs supplier test certificates,
# the GRN row must have Certificate Attached ticked and the certificate file attached.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

QH = "Quality Hold - STPL"
REJECTED = "Rejected - STPL"
STORES = "Stores - STPL"
problems = []


def grn_of(row):
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
        return frappe.db.get_value("Serial No", serial, "reference_name")
    if batch:
        return frappe.db.get_value("Batch", batch, "reference_name")
    return None


for row in doc.items:
    if row.s_warehouse != QH:
        continue
    label = "Row " + str(row.idx) + " (" + row.item_code + ")"
    status = frappe.db.get_value("Quality Inspection", row.quality_inspection, "status") if row.quality_inspection else None
    if status == "Rejected" and row.t_warehouse != REJECTED:
        problems.append(label + ": the inspection rejected it, so it goes to " + REJECTED + ".")
    if row.t_warehouse == STORES and status != "Accepted":
        problems.append(label + ": only material with an Accepted inspection goes to " + STORES + ".")
    if row.project and frappe.db.get_value("Project", row.project, "satcom_certificates_required"):
        grn = grn_of(row)
        ok = False
        if grn:
            for g in frappe.db.sql("select satcom_cert_attached, satcom_cert_file from `tabPurchase Receipt Item`"
                                   " where parent = %s and item_code = %s", (grn, row.item_code), as_dict=True):
                if g.satcom_cert_attached and g.satcom_cert_file:
                    ok = True
        if not ok:
            problems.append(label + ": job " + row.project + " needs the supplier's test certificate. On GRN "
                            + str(grn or "?") + ", tick Certificate Attached on this item's row and attach the certificate.")

if problems:
    frappe.throw("<br>".join(problems), title="QC release rules")
