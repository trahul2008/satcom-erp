"""RETIRED 2026-10-28: removed by satcom_demo_cleanup.py; don't run it again (its codes break
the phase 1 item code rules). Kept for the record.

Sample factory data for the ERPNext demo (satcom-erp). Idempotent: each record is created
only if missing, so a rerun adds nothing twice. Run (after satcom_factory_setup.run):
    bench --site frontend execute erpnext.satcom_sample_data.run

Story: a control-panel maker. Raw parts are bought, the enclosure is powder-coated by an outside
vendor (subcontracting), then the panel is assembled in-house on a Work Order.
"""
import frappe

ABBR = "STPL"
COMPANY = "Satcom Technologies Pvt Ltd"


def _log(msg):
    print(f"[sample] {msg}")


def _ensure(doctype, name, values, submit=False):
    if frappe.db.exists(doctype, name):
        return frappe.get_doc(doctype, name)
    doc = frappe.get_doc({"doctype": doctype, **values}).insert()
    if submit:
        doc.submit()
    _log(f"{doctype}: {doc.name}")
    return doc


def _master_data():
    for sg in ("Raw Material", "Services"):
        if not frappe.db.exists("Supplier Group", sg):
            frappe.get_doc({"doctype": "Supplier Group", "supplier_group_name": sg,
                            "parent_supplier_group": "All Supplier Groups"}).insert()
    for name, group in (("Precision Metals Pvt Ltd", "Raw Material"),
                        ("Bharat Electricals", "Raw Material"),
                        ("Sunrise Powder Coaters", "Services")):
        _ensure("Supplier", name, {"supplier_name": name, "supplier_group": group,
                                   "supplier_type": "Company", "country": "India"})
    _ensure("Customer", "Demo Industries Ltd",
            {"customer_name": "Demo Industries Ltd", "customer_type": "Company",
             "customer_group": "Commercial", "territory": "India"})

    items = [
        # code, name, group, uom, extra
        ("RM-STEEL-SHEET", "Steel Sheet 1.6mm", "Raw Material", "Kg", {}),
        ("RM-ENCLOSURE-BLANK", "Enclosure Blank (unpainted)", "Raw Material", "Nos", {}),
        ("RM-CONTACTOR", "Contactor 32A", "Raw Material", "Nos", {}),
        ("RM-MCB", "MCB 16A", "Raw Material", "Nos", {}),
        ("RM-COPPER-WIRE", "Copper Wire 2.5 sqmm", "Raw Material", "Meter",
         {"has_batch_no": 1, "create_new_batch": 1, "batch_number_series": "WIRE-.####"}),
        ("RM-SCREW-M6", "Screw M6", "Consumable", "Nos", {}),
        ("SA-ENCLOSURE-PAINTED", "Enclosure, powder coated", "Sub Assemblies", "Nos", {"is_sub_contracted_item": 1}),
        ("SRV-POWDER-COATING", "Powder coating (job work)", "Services", "Nos",
         {"is_stock_item": 0}),
        ("FG-MCP-001", "Motor Control Panel 3-phase", "Finished Goods", "Nos",
         {"has_serial_no": 1, "serial_no_series": "MCP-.####"}),
    ]
    for code, name, group, uom, extra in items:
        _ensure("Item", code, {"item_code": code, "item_name": name, "item_group": group,
                               "stock_uom": uom, "is_stock_item": 1, "include_item_in_manufacturing": 1,
                               "valuation_rate": 0, **extra})
    # purchase-side flag for the parts and the service
    for code in ("SRV-POWDER-COATING",):
        frappe.db.set_value("Item", code, "is_purchase_item", 1)


def _workstations():
    for name, rate in (("Assembly Bench", 250), ("Test Bench", 300)):
        _ensure("Workstation", name, {"workstation_name": name, "hour_rate": rate,
                                      "working_hours": [{"start_time": "09:00:00", "end_time": "18:00:00"}]})
    for name, ws in (("Panel Wiring", "Assembly Bench"), ("Panel Testing", "Test Bench")):
        _ensure("Operation", name, {"name": name, "workstation": ws})


def _boms():
    # 1. the coated enclosure: made from the blank, sent to the coater
    enc = frappe.db.get_value("BOM", {"item": "SA-ENCLOSURE-PAINTED", "docstatus": 1}, "name")
    if not enc:
        doc = frappe.get_doc({
            "doctype": "BOM", "item": "SA-ENCLOSURE-PAINTED", "quantity": 1, "company": COMPANY,
            "rm_cost_as_per": "Valuation Rate", "items": [
                {"item_code": "RM-ENCLOSURE-BLANK", "qty": 1, "rate": 1200, "source_warehouse": f"Raw Material - {ABBR}"}]}).insert()
        doc.submit()
        enc = doc.name
        _log(f"BOM: {enc}")
    # 2. subcontracting BOM: service item -> finished good via that BOM
    if not frappe.db.exists("Subcontracting BOM", {"finished_good": "SA-ENCLOSURE-PAINTED"}):
        frappe.get_doc({
            "doctype": "Subcontracting BOM", "finished_good": "SA-ENCLOSURE-PAINTED",
            "finished_good_qty": 1, "finished_good_bom": enc,
            "service_item": "SRV-POWDER-COATING", "service_item_qty": 1, "is_active": 1}).insert()
        _log("Subcontracting BOM: SRV-POWDER-COATING -> SA-ENCLOSURE-PAINTED")
    # 3. the panel, with operations
    if not frappe.db.get_value("BOM", {"item": "FG-MCP-001", "docstatus": 1}, "name"):
        doc = frappe.get_doc({
            "doctype": "BOM", "item": "FG-MCP-001", "quantity": 1, "company": COMPANY,
            "with_operations": 1, "rm_cost_as_per": "Valuation Rate",
            "operations": [
                {"operation": "Panel Wiring", "workstation": "Assembly Bench", "time_in_mins": 90},
                {"operation": "Panel Testing", "workstation": "Test Bench", "time_in_mins": 30}],
            "items": [
                {"item_code": "SA-ENCLOSURE-PAINTED", "qty": 1, "rate": 1500},
                {"item_code": "RM-CONTACTOR", "qty": 3, "rate": 850},
                {"item_code": "RM-MCB", "qty": 6, "rate": 320},
                {"item_code": "RM-COPPER-WIRE", "qty": 20, "rate": 28},
                {"item_code": "RM-SCREW-M6", "qty": 24, "rate": 2}]}).insert()
        doc.submit()
        _log(f"BOM: {doc.name}")


def _opening_stock():
    if frappe.db.exists("Stock Entry", {"remarks": "Demo opening stock", "docstatus": 1}):
        return
    wh = f"Raw Material - {ABBR}"
    rows = [("RM-STEEL-SHEET", 500, 75), ("RM-ENCLOSURE-BLANK", 40, 1200), ("RM-CONTACTOR", 60, 850),
            ("RM-MCB", 120, 320), ("RM-SCREW-M6", 2000, 2)]
    items = [{"item_code": c, "qty": q, "basic_rate": r, "t_warehouse": wh} for c, q, r in rows]
    # batch-tracked wire: a batch is created for the row (serial/batch fields are enabled)
    batch = _ensure("Batch", "WIRE-DEMO-0001", {"batch_id": "WIRE-DEMO-0001", "item": "RM-COPPER-WIRE"})
    items.append({"item_code": "RM-COPPER-WIRE", "qty": 1000, "basic_rate": 28, "t_warehouse": wh,
                  "use_serial_batch_fields": 1, "batch_no": batch.name})
    se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
                         "company": COMPANY, "remarks": "Demo opening stock", "items": items}).insert()
    se.submit()
    _log(f"Stock Entry (opening stock): {se.name}")


def _transactions():
    today = frappe.utils.nowdate()
    sched = frappe.utils.add_days(today, 14)
    if not frappe.db.exists("Purchase Order", {"supplier": "Bharat Electricals", "docstatus": 0}):
        frappe.get_doc({
            "doctype": "Purchase Order", "supplier": "Bharat Electricals", "company": COMPANY,
            "schedule_date": sched,
            "items": [{"item_code": "RM-CONTACTOR", "qty": 100, "rate": 850, "schedule_date": sched,
                       "warehouse": f"Raw Material - {ABBR}"},
                      {"item_code": "RM-MCB", "qty": 200, "rate": 320, "schedule_date": sched,
                       "warehouse": f"Raw Material - {ABBR}"}]}).insert()
        _log("Purchase Order (draft) for contactors + MCBs")
    if not frappe.db.exists("Purchase Order", {"supplier": "Sunrise Powder Coaters", "docstatus": 0}):
        frappe.get_doc({
            "doctype": "Purchase Order", "supplier": "Sunrise Powder Coaters", "company": COMPANY,
            "is_subcontracted": 1, "schedule_date": sched,
            "supplier_warehouse": f"Subcontractor (Job Work) - {ABBR}",
            "items": [{"item_code": "SRV-POWDER-COATING", "fg_item": "SA-ENCLOSURE-PAINTED",
                       "fg_item_qty": 20, "qty": 20, "rate": 350, "schedule_date": sched,
                       "warehouse": f"Raw Material - {ABBR}"}]}).insert()
        _log("Purchase Order (draft, subcontracted): powder coating 20 enclosures")
    bom = frappe.db.get_value("BOM", {"item": "FG-MCP-001", "docstatus": 1}, "name")
    if bom and not frappe.db.exists("Work Order", {"production_item": "FG-MCP-001"}):
        frappe.get_doc({
            "doctype": "Work Order", "production_item": "FG-MCP-001", "bom_no": bom, "qty": 5,
            "company": COMPANY, "use_multi_level_bom": 0,
            "source_warehouse": f"Raw Material - {ABBR}",
            "wip_warehouse": f"Work In Progress - {ABBR}",
            "fg_warehouse": f"Finished Goods - {ABBR}",
            "planned_start_date": frappe.utils.add_days(today, 3)}).insert()
        _log("Work Order (draft): 5 x FG-MCP-001")


def _project():
    if frappe.db.exists("Project", "Panel Line Commissioning"):
        return
    p = frappe.get_doc({
        "doctype": "Project", "project_name": "Panel Line Commissioning", "company": COMPANY,
        "expected_start_date": frappe.utils.nowdate(),
        "expected_end_date": frappe.utils.add_days(frappe.utils.nowdate(), 45)}).insert()
    _log(f"Project: {p.name}")
    for i, (subject, days) in enumerate((("Procure bench, tools and test rig", 10),
                                         ("Qualify powder-coating vendor", 14),
                                         ("Pilot batch of 5 panels", 25),
                                         ("First customer delivery", 45)), start=1):
        frappe.get_doc({"doctype": "Task", "subject": subject, "project": p.name,
                        "exp_start_date": frappe.utils.add_days(frappe.utils.nowdate(), max(0, days - 10)),
                        "exp_end_date": frappe.utils.add_days(frappe.utils.nowdate(), days)}).insert()
    _log("4 project tasks")


def run():
    _master_data()
    _workstations()
    _boms()
    _opening_stock()
    _transactions()
    _project()
    frappe.db.commit()
    _log("done")
