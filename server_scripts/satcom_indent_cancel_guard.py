# Satcom Indent - cancel guard  (Server Script: DocType Event, Material Request, Before Cancel)
# SPEC_PHASE1 3. Source of truth is this file; satcom_p1_purchase.py writes it into ERPNext.
# Only a Satcom Approver cancels an approved indent, with a reason, and only while no PO line
# refers to it. (An indenter who needs a change asks an approver to cancel, then raises a new one.)
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

user = frappe.session.user
problems = []
if user != "Administrator" and not frappe.db.exists("Has Role", {"parenttype": "User", "parent": user,
                                                                 "role": "Satcom Approver"}):
    problems.append("Only a Satcom Approver can cancel an approved indent. Ask an approver, then raise a new indent.")
if not (doc.satcom_cancel_reason or "").strip():
    problems.append("Enter the Cancel Reason first.")
po = frappe.db.get_value("Purchase Order Item", {"material_request": doc.name, "docstatus": ["<", 2]}, "parent")
if po:
    problems.append("Purchase Order " + frappe.bold(po) + " refers to this indent: cancel that PO line first.")
if problems:
    frappe.throw("<br>".join(problems), title="Cancel indent")
# Frappe's cancel leaves the workflow state at "Approved"; show what happened
doc.workflow_state = "Cancelled"
