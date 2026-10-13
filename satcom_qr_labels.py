"""Printable QR labels for the ERPNext demo (satcom-erp). Idempotent (re-creates the formats).

Creates a Print Format "Satcom QR Label" on Item, Batch, Serial No, Warehouse, Work Order and
Job Card: a 100 x 50 mm label with the QR (the stock Barcode field `satcom_qr`, options
'qrcode') on the left and the identifying fields on the right. Run:
    bench --site frontend execute erpnext.satcom_qr_labels.run
Print from any of those records: Menu -> Print -> pick "Satcom QR Label - <doctype>" and set
Letterhead to "No Letterhead" (the default company letterhead is for invoices; on Item/Batch it
has no company to read and errors).
"""
import json

import frappe

FORMAT = "Satcom QR Label"

# doctype -> (big line fieldname, [other fields])
LAYOUTS = {
    "Item": ("item_code", ["item_name", "item_group", "stock_uom"]),
    "Batch": ("batch_id", ["item", "item_name", "expiry_date"]),
    "Serial No": ("serial_no", ["item_code", "item_name", "warehouse"]),
    "Warehouse": ("warehouse_name", ["company", "parent_warehouse"]),
    "Work Order": ("name", ["production_item", "item_name", "qty", "planned_start_date"]),
    "Job Card": ("name", ["work_order", "production_item", "operation", "workstation"]),
}

LABEL_CSS = """
@page { size: 100mm 50mm; margin: 0; }
.print-format { padding: 0 !important; }
.print-format .section-break { margin: 0 !important; }
.print-format svg, .print-format img { max-height: 40mm; }
"""


def _layout(doctype, title_field, others):
    meta = frappe.get_meta(doctype)
    fields = [{"fieldtype": meta.get_field(f).fieldtype if meta.get_field(f) else "Data",
               "fieldname": f, "label": (meta.get_field(f).label if meta.get_field(f) else f)}
              for f in [title_field, *others] if f == "name" or meta.has_field(f)]
    # `name` is not a docfield; print it as plain data
    for f in fields:
        if f["fieldname"] == "name":
            f.update({"fieldtype": "Data", "label": "ID"})
    return {
        "sections": [{
            "label": "",
            "columns": [
                {"label": "", "fields": [{"fieldtype": "Barcode", "fieldname": "satcom_qr", "label": ""}]},
                {"label": "", "fields": fields},
            ],
        }],
    }


def run():
    for doctype, (title_field, others) in LAYOUTS.items():
        name = f"{FORMAT} - {doctype}"
        if frappe.db.exists("Print Format", name):
            frappe.delete_doc("Print Format", name, force=1)
        frappe.get_doc({
            "doctype": "Print Format", "name": name, "doc_type": doctype,
            "print_format_builder_beta": 1, "custom_format": 0, "standard": "No",
            "margin_top": 3, "margin_bottom": 3, "margin_left": 3, "margin_right": 3,
            "show_section_headings": 0, "font_size": 12, "css": LABEL_CSS,
            "format_data": json.dumps(_layout(doctype, title_field, others)),
        }).insert()
        print(f"[labels] {name}")
    frappe.db.commit()


def render_check():
    """Render each format on a real record and report whether a QR image is in the HTML."""
    from frappe.utils.print_format_generator import get_html

    samples = {
        "Item": "FG-MCP-001",
        "Batch": "WIRE-DEMO-0001",
        "Work Order": frappe.db.get_value("Work Order", {}, "name"),
        "Warehouse": f"Raw Material - STPL",
    }
    for dt, docname in samples.items():
        if not docname:
            continue
        # records created before the QR field existed (or by bulk code paths) get it filled here
        if frappe.db.get_value(dt, docname, "satcom_qr") != docname:
            frappe.db.set_value(dt, docname, "satcom_qr", docname)
        html = get_html(dt, docname, f"{FORMAT} - {dt}", no_letterhead=1)
        print(f"[labels] {dt} {docname}: qr={'data:image/svg+xml;base64' in html} len={len(html)}")
