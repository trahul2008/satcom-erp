"""Phase 1 foundation for satcom-erp (SPEC_PHASE1.md section 2). Idempotent.

Run (after satcom_demo_cleanup.run):
    bench --site frontend execute erpnext.satcom_p1_foundation.run
Each step compares before it writes and prints only what it changed, so a second run reports
"0 changes". Built so far: 2.1 settings.
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"

_changes = []


def _log(msg):
    print(f"[p1-foundation] {msg}")


def _set_values(doctype, name, values):
    """Set fields on one record (name=None for a single doctype), saving only if something differs."""
    doc = frappe.get_single(doctype) if name is None else frappe.get_doc(doctype, name)
    diff = {f: v for f, v in values.items() if doc.get(f) != v}
    if not diff:
        return
    for field, value in diff.items():
        if not doc.meta.has_field(field):
            frappe.throw(f"{doctype} has no field {field} in this version")
        _changes.append(f"{doctype}{' ' + name if name else ''}: {field} {doc.get(field)!r} -> {value!r}")
        _log(_changes[-1])
        doc.set(field, value)
    doc.save()


# 2.1 Settings -------------------------------------------------------------------------------

def settings():
    # Perpetual inventory off, so stock never posts GL entries (accounts stay in Tally).
    _set_values("Company", COMPANY, {"enable_perpetual_inventory": 0})
    active_gl = frappe.db.count("GL Entry", {"is_cancelled": 0})
    if active_gl:
        frappe.throw(f"{active_gl} active GL entries exist; accounts must stay in Tally")
    # Valuation stays FIFO (OPEN, spec section 11): checked, never changed here.
    valuation = frappe.db.get_single_value("Stock Settings", "valuation_method")
    if valuation != "FIFO":
        frappe.throw(f"Stock Settings valuation method is {valuation}, spec keeps FIFO (open item)")
    _set_values("Buying Settings", None, {
        "supp_master_name": "Supplier Name",
        "po_required": "No",
        "pr_required": "No",
        "maintain_same_rate": 0,  # POs must allow the approved quotation's rate
    })


def run():
    _changes.clear()
    settings()
    frappe.db.commit()
    frappe.clear_cache()
    _log(f"done: {len(_changes)} changes")
