# Satcom PO - approval guard  (Server Script: DocType Event, Purchase Order, Before Submit)
# SPEC_PHASE1 4.2. Source of truth is this file; satcom_p1_purchase_orders.py writes it into ERPNext.
# Submitting a PO = approving it. Frappe lets anyone with submit rights (Purchase User) submit a
# Draft directly and then moves it to "Approved" itself, so the workflow's checks never run (same
# gap as on indents). Allow a submit only from "Pending Approval", by a Satcom Approver who did
# not raise the PO (no self approval).
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

user = frappe.session.user
if user != "Administrator":
    saved_state = frappe.db.get_value("Purchase Order", doc.name, "workflow_state")
    is_approver = frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": "Satcom Approver"})
    if saved_state != "Pending Approval":
        frappe.throw("A purchase order is approved from Pending Approval only: use Submit for Approval first.",
                     title="Purchase order approval")
    if not is_approver:
        frappe.throw("Only a Satcom Approver can approve a purchase order.", title="Purchase order approval")
    if user == doc.owner:
        frappe.throw("You raised this purchase order, so another approver has to approve it.",
                     title="Purchase order approval")
