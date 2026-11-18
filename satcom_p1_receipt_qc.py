"""Phase 1 goods receipt and incoming QC for satcom-erp (SPEC_PHASE1.md section 5). Idempotent.

Run after satcom_p1_foundation.run (copy server_scripts and client_scripts to
/tmp/satcom_scripts first):
    bench --site frontend execute erpnext.satcom_p1_receipt_qc.run
Prints only what it changed; a second run reports "0 changes".
Interim (decision 6 Nov, QC before section 4): a GRN may be made without a PO; Buying Settings
"Purchase Order Required" stays No until section 4 goes live and switches it to Yes
(satcom_p1_purchase_orders.go_live).
"""
import frappe

from erpnext import satcom_p1_foundation as f

QH = "Quality Hold - STPL"
QI_TEMPLATE = "Standard checks"
# starter template parameters (QC edits the template in the UI; this only adds missing ones)
QI_PARAMETERS = ["Visual damage", "Part no / MPN matches", "Qty matches DC", "Packaging and ESD intact",
                 "Documents received"]
QC_RELEASE_TYPE = "QC Release"
DISPOSITIONS = ["Return to Vendor", "Scrap", "Use under Concession"]
PENDING_QC_REPORT = "Satcom Pending QC"
PENDING_QC_SQL = """
SELECT x.item_code AS "Item:Link/Item:150",
       x.serial_or_batch AS "Serial / Batch:Data:180",
       x.qty AS "Qty:Float:70",
       x.grn AS "GRN:Link/Purchase Receipt:150",
       pr.supplier AS "Supplier:Link/Supplier:160",
       x.job AS "Job:Link/Project:110",
       pr.posting_date AS "Received:Date:100",
       DATEDIFF(CURDATE(), pr.posting_date) AS "Days Waiting:Int:100"
FROM (
    SELECT sn.item_code, sn.name AS serial_or_batch, 1 AS qty, sn.reference_name AS grn,
           sn.satcom_received_for_job AS job
      FROM `tabSerial No` sn
     WHERE sn.warehouse = 'Quality Hold - STPL'
    UNION ALL
    SELECT b.item, b.name, SUM(sbe.qty), b.reference_name, b.satcom_received_for_job
      FROM `tabSerial and Batch Entry` sbe
      JOIN `tabSerial and Batch Bundle` sbb ON sbb.name = sbe.parent
      JOIN `tabBatch` b ON b.name = sbe.batch_no
     WHERE sbb.warehouse = 'Quality Hold - STPL' AND sbb.docstatus = 1 AND sbb.is_cancelled = 0
     GROUP BY b.name, b.item, b.reference_name, b.satcom_received_for_job
    HAVING SUM(sbe.qty) > 0
) x
LEFT JOIN `tabPurchase Receipt` pr ON pr.name = x.grn
ORDER BY pr.posting_date, x.grn, x.serial_or_batch
"""
PENDING_QC_ROLES = ["Stock User", "Stock Manager", "Quality Manager"]


def _ensure(doctype, name, values):
    if not frappe.db.exists(doctype, name):
        frappe.get_doc({"doctype": doctype, **values}).insert()
        f._change(f"{doctype} {name}")


def receipt():
    # 5.1 GRN header: vendor invoice and DC, required on receipts (not on returns)
    on_receipt = "eval:!doc.is_return"
    f._custom_field("Purchase Receipt", "satcom_vendor_section", label="Vendor Documents",
                    fieldtype="Section Break", insert_after="supplier_delivery_note")
    f._custom_field("Purchase Receipt", "satcom_vendor_invoice_no", label="Vendor Invoice No", fieldtype="Data",
                    insert_after="satcom_vendor_section", mandatory_depends_on=on_receipt, depends_on=on_receipt)
    f._custom_field("Purchase Receipt", "satcom_vendor_invoice_date", label="Vendor Invoice Date", fieldtype="Date",
                    insert_after="satcom_vendor_invoice_no", mandatory_depends_on=on_receipt, depends_on=on_receipt)
    f._custom_field("Purchase Receipt", "satcom_vendor_cb", fieldtype="Column Break", insert_after="satcom_vendor_invoice_date")
    f._custom_field("Purchase Receipt", "satcom_vendor_dc_no", label="Vendor DC No", fieldtype="Data",
                    insert_after="satcom_vendor_cb", mandatory_depends_on=on_receipt, depends_on=on_receipt)
    f._custom_field("Purchase Receipt", "satcom_vendor_dc_date", label="Vendor DC Date", fieldtype="Date",
                    insert_after="satcom_vendor_dc_no", mandatory_depends_on=on_receipt, depends_on=on_receipt)
    # 5.3 return to vendor = a Purchase Return; it records why
    f._custom_field("Purchase Receipt", "satcom_disposition", label="Disposition", fieldtype="Data", read_only=1,
                    insert_after="satcom_vendor_dc_date", depends_on="eval:doc.is_return")
    f._custom_field("Purchase Receipt", "satcom_disposition_reason", label="Disposition Reason", fieldtype="Small Text",
                    insert_after="satcom_disposition", depends_on="eval:doc.is_return",
                    description="Why the rejected material goes back (required when returning from Rejected - STPL)")
    # 5.1 certificates per GRN row (can be added after submit, before QC release)
    f._custom_field("Purchase Receipt Item", "satcom_cert_attached", label="Certificate Attached", fieldtype="Check",
                    insert_after="project", allow_on_submit=1)
    f._custom_field("Purchase Receipt Item", "satcom_cert_file", label="Test Certificate", fieldtype="Attach",
                    insert_after="satcom_cert_attached", allow_on_submit=1)
    # 5.1 the job each serial / batch was received for
    for dt in ("Serial No", "Batch"):
        f._custom_field(dt, "satcom_received_for_job", label="Received for Job", fieldtype="Link", options="Project",
                        read_only=1, in_standard_filter=1, insert_after="item_code" if dt == "Serial No" else "item")

    f._server_script("Satcom GRN - rules", "Purchase Receipt", "Before Save", "satcom_grn_rules.py")
    f._server_script("Satcom GRN - submit guard", "Purchase Receipt", "Before Submit", "satcom_grn_submit_guard.py")
    f._server_script("Satcom GRN - job on serials and batches", "Purchase Receipt", "After Submit",
                     "satcom_grn_job_to_serials.py")
    for dt in ("Serial No", "Batch"):
        f._server_script(f"Satcom {dt} - job from GRN", dt, "Before Save", "satcom_received_for_job.py")
    f._client_script("Satcom GRN", "Purchase Receipt", "satcom_grn.js")


def qc():
    # 5.2 rejected inspections are handled by the Stock Entry rules, not by ERPNext's blanket Stop
    f._set_values("Stock Settings", None, {"action_if_quality_inspection_is_rejected": "Warn",
                                           "action_if_quality_inspection_is_not_submitted": "Stop"})
    for p in QI_PARAMETERS:
        _ensure("Quality Inspection Parameter", p, {"parameter": p})
    if not frappe.db.exists("Quality Inspection Template", QI_TEMPLATE):
        frappe.get_doc({"doctype": "Quality Inspection Template", "quality_inspection_template_name": QI_TEMPLATE,
                        "item_quality_inspection_parameter": [{"specification": p, "numeric": 0, "value": "OK"}
                                                              for p in QI_PARAMETERS]}).insert()
        f._change(f"Quality Inspection Template {QI_TEMPLATE}")
    # default on every item in a Satcom group that has none (new items get it from the item rules)
    groups = frappe.get_all("Item Group", filters={"satcom_prefix": ["is", "set"]}, pluck="name")
    for item in frappe.get_all("Item", filters={"item_group": ["in", groups], "quality_inspection_template": ["is", "not set"]},
                               pluck="name"):
        frappe.db.set_value("Item", item, "quality_inspection_template", QI_TEMPLATE)
        f._change(f"Item {item}: Quality Inspection Template {QI_TEMPLATE}")

    f._custom_field("Quality Inspection", "satcom_job", label="Job", fieldtype="Link", options="Project", read_only=1,
                    insert_after="reference_name")
    f._custom_field("Quality Inspection", "satcom_inspection_level", label="Inspection Level (from the job)",
                    fieldtype="Data", read_only=1, insert_after="satcom_job")
    f._server_script("Satcom Quality Inspection - level", "Quality Inspection", "Before Save", "satcom_qi_level.py")

    _ensure("Stock Entry Type", QC_RELEASE_TYPE, {"__newname": QC_RELEASE_TYPE, "purpose": "Material Transfer"})
    f._custom_field("Stock Entry", "satcom_disposition_section", label="Rejected Material", fieldtype="Section Break",
                    insert_after="stock_entry_type", collapsible=0,
                    depends_on='eval:(doc.items || []).some(r => r.s_warehouse === "Rejected - STPL") || doc.satcom_disposition')
    f._custom_field("Stock Entry", "satcom_disposition", label="Disposition", fieldtype="Select",
                    options="\n" + "\n".join(DISPOSITIONS), insert_after="satcom_disposition_section",
                    description="Required for anything leaving Rejected - STPL. Return to Vendor = Purchase Return on the GRN.")
    f._custom_field("Stock Entry", "satcom_disposition_reason", label="Disposition Reason", fieldtype="Small Text",
                    insert_after="satcom_disposition")
    f._custom_field("Stock Entry", "satcom_concession_approved_by", label="Concession Approved By", fieldtype="Link",
                    options="User", insert_after="satcom_disposition_reason",
                    depends_on='eval:doc.satcom_disposition=="Use under Concession"',
                    description="Set by the Satcom Approver themselves, when Satcom Settings asks for concession approval")
    f._server_script("Satcom Stock Entry - rules", "Stock Entry", "Before Save", "satcom_stock_entry_rules.py")
    f._server_script("Satcom QC release - rules", "Stock Entry", "Before Submit", "satcom_qc_release_rules.py")

    # 5.2 Pending QC view
    wanted = {"ref_doctype": "Purchase Receipt", "report_type": "Query Report", "is_standard": "No",
              "module": "Stock", "query": PENDING_QC_SQL.strip(), "disabled": 0}
    if not frappe.db.exists("Report", PENDING_QC_REPORT):
        frappe.get_doc({"doctype": "Report", "report_name": PENDING_QC_REPORT, **wanted,
                        "roles": [{"role": r} for r in PENDING_QC_ROLES]}).insert()
        f._change(f"report {PENDING_QC_REPORT}")
    else:
        doc = frappe.get_doc("Report", PENDING_QC_REPORT)
        diff = {k: v for k, v in wanted.items() if doc.get(k) != v}
        have_roles = sorted(r.role for r in doc.roles)
        if diff or have_roles != sorted(PENDING_QC_ROLES):
            doc.update(diff)
            doc.set("roles", [{"role": r} for r in PENDING_QC_ROLES])
            doc.save()
            f._change(f"report {PENDING_QC_REPORT} updated")


def run():
    f._changes.clear()
    receipt()
    qc()
    frappe.db.commit()
    frappe.clear_cache()
    f._log(f"receipt-qc done: {len(f._changes)} changes")
