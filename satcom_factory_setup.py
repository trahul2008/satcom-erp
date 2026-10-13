"""Factory-oriented configuration for the ERPNext demo (satcom-erp). Idempotent.

Installed into the backend container and run with:
    bench --site frontend execute erpnext.satcom_factory_setup.run
(see erpnext/README.md). Everything is stock ERPNext: standard doctypes, standard settings,
no custom app. Each step skips what already exists, so a rerun is safe.
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"
ABBR = "STPL"

# (warehouse, parent-warehouse-type) - ERPNext already creates Stores, Work In Progress,
# Finished Goods and Goods In Transit for a new company.
EXTRA_WAREHOUSES = [
    "Raw Material",
    "Subcontractor (Job Work)",
    "Quality Hold",
    "Scrap",
]
ITEM_GROUPS = ["Sub Assemblies", "Packaging", "Tools & Spares", "Consumable"]


def _log(msg):
    print(f"[satcom-setup] {msg}")


def _setup_wizard():
    if frappe.is_setup_complete():
        _log("setup wizard already complete")
        return
    from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

    year = frappe.utils.getdate().year
    start_year = year if frappe.utils.getdate().month >= 4 else year - 1
    setup_complete({
        "language": "English",
        "country": "India",
        "timezone": "Asia/Kolkata",
        "currency": "INR",
        "company_name": COMPANY,
        "company_abbr": ABBR,
        "chart_of_accounts": "Standard",
        "fy_start_date": f"{start_year}-04-01",
        "fy_end_date": f"{start_year + 1}-03-31",
        "full_name": "Administrator",
        "enable_telemetry": 0,
    })
    frappe.db.commit()
    _log("setup wizard completed")


def _warehouses():
    root = f"All Warehouses - {ABBR}"
    for name in EXTRA_WAREHOUSES:
        full = f"{name} - {ABBR}"
        if frappe.db.exists("Warehouse", full):
            continue
        frappe.get_doc({
            "doctype": "Warehouse", "warehouse_name": name, "company": COMPANY,
            "parent_warehouse": root, "is_group": 0,
        }).insert()
        _log(f"warehouse {full}")


def _item_groups():
    for name in ITEM_GROUPS:
        if frappe.db.exists("Item Group", name):
            continue
        frappe.get_doc({"doctype": "Item Group", "item_group_name": name,
                        "parent_item_group": "All Item Groups", "is_group": 0}).insert()
        _log(f"item group {name}")


def _set_single(doctype, values):
    meta = frappe.get_meta(doctype)
    doc = frappe.get_single(doctype)
    for field, value in values.items():
        if meta.has_field(field):
            doc.set(field, value)
        else:
            _log(f"  ({doctype}.{field} not present in this version - skipped)")
    doc.save()
    _log(f"{doctype} updated")


def _settings():
    wh = lambda n: f"{n} - {ABBR}"  # noqa: E731
    # WIP / finished goods / scrap defaults live on the Company in this version.
    company = frappe.get_doc("Company", COMPANY)
    company.default_wip_warehouse = wh("Work In Progress")
    company.default_fg_warehouse = wh("Finished Goods")
    company.default_scrap_warehouse = wh("Scrap")
    company.save()
    _log("Company default WIP / FG / scrap warehouses set")
    _set_single("Stock Settings", {
        "allow_negative_stock": 0,
        "default_warehouse": wh("Stores"),
        "use_serial_batch_fields": 1,       # type serial / batch straight on the row (scan friendly)
        "auto_insert_price_list_rate_if_missing": 1,
    })
    _set_single("Manufacturing Settings", {
        "backflush_raw_materials_based_on": "BOM",
        "update_bom_costs_automatically": 1,
        "capacity_planning_for_days": 30,
        "mins_between_operations": 10,
    })
    _set_single("Buying Settings", {
        "backflush_raw_materials_of_subcontract_based_on": "BOM",
        "maintain_same_rate": 1,
    })


def _qr_fields():
    """A scannable QR on the records a factory labels and tracks. The field is a stock 'Barcode'
    fieldtype with options 'qrcode'; it is filled with the record's own name, so scanning a label
    in any ERPNext scan field (Stock Entry, Delivery Note, Work Order...) finds the record."""
    targets = {
        "Item": "item_code",
        "Batch": "batch_id",
        "Serial No": "serial_no",
        "Warehouse": "name",
        "Work Order": "name",
        "Job Card": "name",
    }
    for dt in targets:
        fn = "satcom_qr"
        if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fn}):
            _qr_script(dt)
            continue
        meta = frappe.get_meta(dt)
        insert_after = meta.fields[1].fieldname if len(meta.fields) > 1 else None
        frappe.get_doc({
            "doctype": "Custom Field", "dt": dt, "fieldname": fn, "label": "QR Label",
            "fieldtype": "Barcode", "options": "qrcode", "read_only": 1, "no_copy": 1,
            "insert_after": insert_after, "print_hide": 0,
        }).insert()
        _log(f"custom field {dt}.{fn}")
        _qr_script(dt)


def _qr_script(dt):
    """Fill satcom_qr with the record's name on every save (needs server_script_enabled)."""
    title = f"Satcom QR label - {dt}"
    if frappe.db.exists("Server Script", title):
        return
    frappe.get_doc({
        "doctype": "Server Script", "name": title, "script_type": "DocType Event",
        "reference_doctype": dt, "doctype_event": "Before Save",
        "script": "doc.satcom_qr = doc.name", "disabled": 0,
    }).insert()
    _log(f"server script {title}")


def run():
    _setup_wizard()
    _warehouses()
    _item_groups()
    _settings()
    _qr_fields()
    frappe.db.commit()
    frappe.clear_cache()
    _log("done")
