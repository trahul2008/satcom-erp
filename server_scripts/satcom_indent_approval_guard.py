# Satcom Indent - approval guard  (Server Script: DocType Event, Material Request, Before Submit)
# SPEC_PHASE1 3. Source of truth is this file; satcom_p1_purchase.py writes it into ERPNext.
# Submitting an indent = approving it. Frappe lets anyone with submit rights (Stock User,
# Purchase User) submit a Draft directly and then moves it to "Approved" itself, so the
# workflow's checks never run. Allow a submit only from "Pending Approval", by a Satcom Approver
# who did not raise the indent (no self approval).
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

user = frappe.session.user
if user != "Administrator":
    saved_state = frappe.db.get_value("Material Request", doc.name, "workflow_state")
    is_approver = frappe.db.exists("Has Role", {"parenttype": "User", "parent": user, "role": "Satcom Approver"})
    if saved_state != "Pending Approval":
        frappe.throw("An indent is approved from Pending Approval only: use Submit for Approval first.",
                     title="Indent approval")
    if not is_approver:
        frappe.throw("Only a Satcom Approver can approve an indent.", title="Indent approval")
    if user == doc.owner:
        frappe.throw("You raised this indent, so another approver has to approve it.", title="Indent approval")
