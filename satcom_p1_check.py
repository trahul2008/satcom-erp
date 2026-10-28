"""Phase 1 acceptance check for satcom-erp (SPEC_PHASE1.md section 10). Read-only.

    bench --site frontend execute erpnext.satcom_p1_check.verify
Prints PASS/FAIL per line and a summary. It grows with each section as it is built; the DEMO
scenario (create_demo / cleanup, spec section 10) is added once the sections it needs exist.
Built so far: 1 demo cleanup, 2.1 settings.
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"

_results = []


def _check(label, ok, detail=""):
    _results.append(bool(ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail and not ok else ''}")


def _section_1_cleanup():
    demo_items = ["FG-MCP-001", "SA-ENCLOSURE-PAINTED", "SRV-POWDER-COATING", "RM-STEEL-SHEET",
                  "RM-ENCLOSURE-BLANK", "RM-CONTACTOR", "RM-MCB", "RM-COPPER-WIRE", "RM-SCREW-M6"]
    left = frappe.get_all("Item", filters={"name": ["in", demo_items]}, pluck="name")
    _check("1  demo sample items removed", not left, left)
    sup = frappe.get_all("Supplier", filters={"name": ["in", ["Precision Metals Pvt Ltd", "Bharat Electricals",
                                                               "Sunrise Powder Coaters"]]}, pluck="name")
    _check("1  demo suppliers removed", not sup, sup)
    _check("1  demo project removed", not frappe.db.exists("Project", {"project_name": "Panel Line Commissioning"}))
    _check("1  'Assembly' operation kept", frappe.db.exists("Operation", "Assembly"))


def _section_2_1_settings():
    _check("2.1 perpetual inventory off",
           not frappe.db.get_value("Company", COMPANY, "enable_perpetual_inventory"))
    gl = frappe.db.count("GL Entry", {"is_cancelled": 0})
    _check("2.1 no active GL entries", gl == 0, f"{gl} active")
    v = frappe.db.get_single_value("Stock Settings", "valuation_method")
    _check("2.1 valuation method FIFO (open item)", v == "FIFO", v)
    bs = frappe.get_single("Buying Settings")
    _check("2.1 suppliers named by supplier name", bs.supp_master_name == "Supplier Name", bs.supp_master_name)
    _check("2.1 PO not required for receipt", bs.po_required == "No", bs.po_required)
    _check("2.1 Purchase Receipt not required", bs.pr_required == "No", bs.pr_required)
    _check("2.1 maintain same rate off", not bs.maintain_same_rate, bs.maintain_same_rate)


def verify():
    _results.clear()
    _section_1_cleanup()
    _section_2_1_settings()
    failed = _results.count(False)
    print(f"{len(_results) - failed}/{len(_results)} PASS" + (f", {failed} FAIL" if failed else ""))
