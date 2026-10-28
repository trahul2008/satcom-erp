"""Remove the 2026-10-13 demo sample data (satcom_sample_data.py) from satcom-erp. Idempotent.

Approved by Rahul 2026-10-28 (SPEC_PHASE1.md section 1). Back up first. Run:
    bench --site frontend execute erpnext.satcom_demo_cleanup.run --kwargs "{'dry_run': 1}"
    bench --site frontend execute erpnext.satcom_demo_cleanup.run
A dry run does every step and then rolls the transaction back, so it shows what would be blocked.

Submitted documents are cancelled, then everything is deleted in dependency order. For the
opening-stock entry only, its cancelled ledger rows are deleted too (option C, 2026-10-28):
v16 keeps them as live links that block deleting the batch and items. They are selected by
voucher_type + voucher_no and nothing else. Document counters are not reset. Kept: supplier
groups, item groups, the "Assembly" operation (all created by ERPNext at setup).
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"
OPENING_STOCK = "MAT-STE-2026-00001"
PROJECT_NAME = "Panel Line Commissioning"
ITEMS = [
    "FG-MCP-001", "SA-ENCLOSURE-PAINTED", "SRV-POWDER-COATING", "RM-STEEL-SHEET",
    "RM-ENCLOSURE-BLANK", "RM-CONTACTOR", "RM-MCB", "RM-COPPER-WIRE", "RM-SCREW-M6",
]
BATCHES = ["WIRE-DEMO-0001"]
OPERATIONS = ["Panel Wiring", "Panel Testing"]
WORKSTATIONS = ["Assembly Bench", "Test Bench"]
SUPPLIERS = ["Precision Metals Pvt Ltd", "Bharat Electricals", "Sunrise Powder Coaters"]
CUSTOMERS = ["Demo Industries Ltd"]
# Every v16 doctype with voucher_type + voucher_no columns (checked on the site 2026-10-28).
VOUCHER_TABLES = [
    "Stock Ledger Entry", "GL Entry", "Serial and Batch Bundle", "Serial and Batch Entry",
    "Repost Item Valuation", "Repost Accounting Ledger Items", "Repost Payment Ledger Items",
    "Payment Ledger Entry", "Advance Payment Ledger Entry", "Stock Reservation Entry",
    "Unreconcile Payment", "Ledger Health",
]

_changes = []


def _log(msg):
    print(f"[cleanup] {msg}")


def _did(msg):
    _changes.append(msg)
    _log(msg)


def _cancel(doctype, name):
    doc = frappe.get_doc(doctype, name)
    if doc.docstatus == 1:
        doc.cancel()
        _did(f"cancelled {doctype} {name}")


def _delete(doctype, name):
    if not frappe.db.exists(doctype, name):
        return
    frappe.delete_doc(doctype, name)
    _did(f"deleted {doctype} {name}")


def _names(doctype, filters):
    return frappe.get_all(doctype, filters=filters, pluck="name")


def _purge_voucher_rows(voucher_type, voucher_no):
    """Delete the ledger rows of one cancelled voucher, selected by voucher_type + voucher_no."""
    if frappe.db.get_value(voucher_type, voucher_no, "docstatus") != 2:
        frappe.throw(f"{voucher_type} {voucher_no} is not cancelled; not purging its ledger rows")
    for dt in ("Stock Ledger Entry", "GL Entry"):
        if frappe.db.exists(dt, {"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0}):
            frappe.throw(f"{dt} has an active row for {voucher_no}; not purging")
    bundles = _names("Serial and Batch Bundle", {"voucher_type": voucher_type, "voucher_no": voucher_no})
    for dt in VOUCHER_TABLES:
        filters = {"voucher_type": voucher_type, "voucher_no": voucher_no}
        count = frappe.db.count(dt, filters)
        if dt == "Serial and Batch Entry" and bundles:
            # bundle rows, matched by their parent bundle as well (voucher_no may be blank on them)
            count = frappe.db.count(dt, {"parent": ["in", bundles]})
            filters = {"parent": ["in", bundles]}
        if count:
            frappe.db.delete(dt, filters)
            _did(f"purged {count} {dt} row(s) of {voucher_no}")


def _purge_cancel_reposts(before):
    """The cancel queues one Repost Item Valuation per item + warehouse (item_based_reposting is
    on) with no voucher fields, so they can't be found by voucher. Delete only the ones this
    cancel created, and only for the demo items."""
    new = [r for r in frappe.get_all("Repost Item Valuation", fields=["name", "item_code", "voucher_no"])
           if r.name not in before]
    other = [r.name for r in new if r.item_code not in ITEMS and r.voucher_no != OPENING_STOCK]
    if other:
        frappe.throw(f"cancel created repost entries for other items: {other}; not purging")
    if new:
        frappe.db.delete("Repost Item Valuation", {"name": ["in", [r.name for r in new]]})
        _did(f"purged {len(new)} Repost Item Valuation row(s) queued by cancelling {OPENING_STOCK}")


def _check_bins_zero():
    qty_fields = ["actual_qty", "ordered_qty", "reserved_qty", "indented_qty", "planned_qty",
                  "projected_qty", "reserved_qty_for_production", "reserved_qty_for_sub_contract",
                  "reserved_stock"]
    meta = frappe.get_meta("Bin")
    fields = [f for f in qty_fields if meta.has_field(f)]
    for b in frappe.get_all("Bin", filters={"item_code": ["in", ITEMS]}, fields=["name", "item_code", "warehouse", *fields]):
        nonzero = {f: b[f] for f in fields if b[f]}
        if nonzero:
            frappe.throw(f"Bin {b.item_code} / {b.warehouse} not zero: {nonzero}")
    _log(f"bins for demo items all zero ({frappe.db.count('Bin', {'item_code': ['in', ITEMS]})} rows, "
         f"checked {', '.join(fields)})")


def _steps():
    # 1. draft transactions that point at the demo items
    for wo in _names("Work Order", {"production_item": ["in", ITEMS], "docstatus": 0}):
        _delete("Work Order", wo)
    for po in _names("Purchase Order", {"supplier": ["in", SUPPLIERS], "docstatus": 0}):
        _delete("Purchase Order", po)
    for ip in _names("Item Price", {"item_code": ["in", ITEMS]}):
        _delete("Item Price", ip)

    # 2. manufacturing masters: subcontracting BOM, then BOMs (top level first)
    for sb in _names("Subcontracting BOM", {"finished_good": ["in", ITEMS]}):
        _delete("Subcontracting BOM", sb)
    for item in ("FG-MCP-001", "SA-ENCLOSURE-PAINTED"):
        for bom in _names("BOM", {"item": item, "docstatus": 1}):
            _cancel("BOM", bom)
    for item in ("FG-MCP-001", "SA-ENCLOSURE-PAINTED"):
        for bom in _names("BOM", {"item": item}):
            _delete("BOM", bom)

    # 3. the opening stock entry: cancel (reverses stock and GL), remove its cancelled ledger
    #    rows, then the entry itself
    if frappe.db.exists("Stock Entry", OPENING_STOCK):
        reposts_before = set(_names("Repost Item Valuation", {}))
        _cancel("Stock Entry", OPENING_STOCK)
        _purge_voucher_rows("Stock Entry", OPENING_STOCK)
        _purge_cancel_reposts(reposts_before)
        _delete("Stock Entry", OPENING_STOCK)

    # 4. project and its tasks
    for project in _names("Project", {"project_name": PROJECT_NAME}):
        for task in _names("Task", {"project": project}):
            _delete("Task", task)
        _delete("Project", project)

    # 5. remaining masters (Item.on_trash removes the items' Bin rows; they must be all zero)
    _check_bins_zero()
    for b in BATCHES:
        _delete("Batch", b)
    for item in ITEMS:
        _delete("Item", item)
    for op in OPERATIONS:
        _delete("Operation", op)
    for ws in WORKSTATIONS:
        _delete("Workstation", ws)
    for s in SUPPLIERS:
        _delete("Supplier", s)
    for c in CUSTOMERS:
        _delete("Customer", c)


def report():
    """Read-only: what is left of the demo data, and whether any ledger entry is still active."""
    left = {
        "Item": _names("Item", {"name": ["in", ITEMS]}),
        "Batch": _names("Batch", {"name": ["in", BATCHES]}),
        "BOM": _names("BOM", {"item": ["in", ITEMS]}),
        "Work Order": _names("Work Order", {"production_item": ["in", ITEMS]}),
        "Purchase Order": _names("Purchase Order", {"supplier": ["in", SUPPLIERS]}),
        "Project": _names("Project", {"project_name": PROJECT_NAME}),
        "Supplier": _names("Supplier", {"name": ["in", SUPPLIERS]}),
        "Customer": _names("Customer", {"name": ["in", CUSTOMERS]}),
        "Operation": _names("Operation", {"name": ["in", OPERATIONS]}),
        "Workstation": _names("Workstation", {"name": ["in", WORKSTATIONS]}),
    }
    for dt, names in left.items():
        _log(f"left {dt}: {names or 'none'}")
    _log(f"Stock Entry {OPENING_STOCK} docstatus: "
         f"{frappe.db.get_value('Stock Entry', OPENING_STOCK, 'docstatus')}")
    for dt in ("Stock Ledger Entry", "GL Entry"):
        _log(f"{dt} rows: {frappe.db.count(dt)} total, {frappe.db.count(dt, {'is_cancelled': 0})} active")
    nonzero = frappe.db.count("Bin", {"actual_qty": ["!=", 0]})
    _log(f"Bin rows with stock (Stock Balance): {nonzero}")


def _series():
    return dict(frappe.db.sql("select name, current from tabSeries"))


def _keep_series(before):
    """frappe.delete_doc steps a naming series back when the deleted record was its last number;
    put every counter back so old numbers are never reused."""
    after = _series()
    for name, current in before.items():
        now = after.get(name)
        if now is not None and now < current:
            frappe.db.sql("update tabSeries set current=%s where name=%s", (current, name))
            _did(f"kept counter {name} at {current} (delete had stepped it back to {now})")


def run(dry_run=0):
    _changes.clear()
    try:
        before = _series()
        _steps()
        _keep_series(before)
    except Exception:
        frappe.db.rollback()
        _log("FAILED, rolled back")
        raise
    if int(dry_run):
        frappe.db.rollback()
        _log(f"dry run: {len(_changes)} changes, rolled back")
        return
    frappe.db.commit()
    _log(f"done: {len(_changes)} changes")
    report()
