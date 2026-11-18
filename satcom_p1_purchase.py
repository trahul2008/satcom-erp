"""Phase 1 indents for satcom-erp (SPEC_PHASE1.md section 3). Idempotent.

Run after satcom_p1_foundation.run (copy server_scripts to /tmp/satcom_scripts first):
    bench --site frontend execute erpnext.satcom_p1_purchase.run
Prints only what it changed; a second run reports "0 changes".
Section 4 (quotations and purchase orders) is in satcom_p1_purchase_orders.py.
"""
import frappe

from erpnext import satcom_p1_foundation as f

# 3 Indents (Material Request, type Purchase) ------------------------------------------------

INDENT_WORKFLOW = "Satcom Indent Approval"
# state -> (doc_status, role that may edit in this state, indicator style)
INDENT_STATES = {
    "Draft": ("0", "Satcom Indenter", ""),
    "Pending Approval": ("0", "Satcom Approver", "Warning"),
    "Approved": ("1", "Satcom Approver", "Success"),
    "Rejected": ("0", "Satcom Approver", "Danger"),
    # set by Frappe itself when an approved indent is cancelled (cancel guard: approvers only)
    "Cancelled": ("2", "Satcom Approver", "Danger"),
}
# (state, action, next state, allowed role, allow self approval). Every indent needs approval,
# whatever its value (decision 27 Oct); to let small indents through later, give the Approve
# transition a condition or add a second transition with one.
INDENT_TRANSITIONS = [
    ("Draft", "Submit for Approval", "Pending Approval", "Satcom Indenter", 1),
    ("Pending Approval", "Approve", "Approved", "Satcom Approver", 0),
    ("Pending Approval", "Reject", "Rejected", "Satcom Approver", 1),
]
# grid columns (Material Request Item): stock in hand and projected qty next to what is asked for.
# Required By stays in the header (and the row form), so the grid fits on a laptop screen.
INDENT_GRID = {"item_code": 3, "qty": 1, "uom": 1, "warehouse": 2, "actual_qty": 1, "projected_qty": 1}
INDENT_GRID_HIDDEN = ["schedule_date"]
NOTIFICATIONS = {
    "Satcom Indent - waiting for approval": {
        "condition": 'doc.workflow_state == "Pending Approval"',
        "subject": "Indent {{ doc.name }} ({{ doc.satcom_job or 'tools, no job' }}) waits for your approval",
        "recipients": [{"receiver_by_role": "Satcom Approver"}],
    },
    "Satcom Indent - decided": {
        "condition": 'doc.workflow_state in ("Approved", "Rejected")',
        "subject": "Indent {{ doc.name }} was {{ doc.workflow_state | lower }}",
        "message": "Indent {{ doc.name }} ({{ doc.satcom_job or 'tools, no job' }}) was {{ doc.workflow_state | lower }}"
                   "{% if doc.workflow_state == 'Rejected' %}. Reason: {{ doc.satcom_rejection_reason }}{% endif %}",
        "recipients": [{"receiver_by_document_field": "owner"}],
    },
}


def _ensure(doctype, name, values):
    if not frappe.db.exists(doctype, name):
        frappe.get_doc({"doctype": doctype, **values}).insert()
        f._change(f"{doctype} {name}")


def indents():
    f._custom_field("Material Request", "satcom_job", label="Job", fieldtype="Link", options="Project",
                    insert_after="material_request_type", in_list_view=1, in_standard_filter=1,
                    description="The job this material is for. Leave empty only when every row is a tool (TOL).")
    f._custom_field("Material Request", "satcom_rejection_reason", label="Rejection Reason", fieldtype="Small Text",
                    insert_after="satcom_job", no_copy=1,
                    depends_on='eval:["Pending Approval", "Rejected"].includes(doc.workflow_state)',
                    description="Asked for when an approver clicks Reject")
    f._server_script("Satcom Indent - rules", "Material Request", "Before Save", "satcom_indent_rules.py")
    f._server_script("Satcom Indent - approval guard", "Material Request", "Before Submit",
                     "satcom_indent_approval_guard.py")
    f._custom_field("Material Request", "satcom_cancel_reason", label="Cancel Reason", fieldtype="Small Text",
                    insert_after="satcom_rejection_reason", no_copy=1, allow_on_submit=1, read_only=1,
                    depends_on="eval:doc.satcom_cancel_reason")
    f._server_script("Satcom Indent - cancel guard", "Material Request", "Before Cancel",
                     "satcom_indent_cancel_guard.py")
    f._client_script("Satcom Indent", "Material Request", "satcom_indent.js")
    # Required By left the grid: the header date is the one people fill in, so it is mandatory
    f._field_property("Material Request", "schedule_date", "reqd", 1, "Check")

    for field, cols in INDENT_GRID.items():
        f._field_property("Material Request Item", field, "in_list_view", 1, "Check")
        f._field_property("Material Request Item", field, "columns", cols, "Int")
    for field in INDENT_GRID_HIDDEN:
        f._field_property("Material Request Item", field, "in_list_view", 0, "Check")

    for state, (_, _, style) in INDENT_STATES.items():
        _ensure("Workflow State", state, {"workflow_state_name": state, "style": style})
    for _, action, _, _, _ in INDENT_TRANSITIONS:
        _ensure("Workflow Action Master", action, {"workflow_action_name": action})

    wanted = {
        "document_type": "Material Request", "is_active": 1, "send_email_alert": 0, "override_status": 0,
        "workflow_state_field": "workflow_state",
        "states": [{"state": s, "doc_status": d, "allow_edit": r} for s, (d, r, _) in INDENT_STATES.items()],
        "transitions": [{"state": s, "action": a, "next_state": n, "allowed": r, "allow_self_approval": self_ok}
                        for s, a, n, r, self_ok in INDENT_TRANSITIONS],
    }
    if not frappe.db.exists("Workflow", INDENT_WORKFLOW):
        frappe.get_doc({"doctype": "Workflow", "workflow_name": INDENT_WORKFLOW, **wanted}).insert()
        f._change(f"workflow {INDENT_WORKFLOW}")
    else:
        wf = frappe.get_doc("Workflow", INDENT_WORKFLOW)
        have = {
            "document_type": wf.document_type, "is_active": wf.is_active, "send_email_alert": wf.send_email_alert,
            "override_status": wf.override_status, "workflow_state_field": wf.workflow_state_field,
            "states": [{"state": s.state, "doc_status": s.doc_status, "allow_edit": s.allow_edit} for s in wf.states],
            "transitions": [{"state": t.state, "action": t.action, "next_state": t.next_state, "allowed": t.allowed,
                             "allow_self_approval": t.allow_self_approval} for t in wf.transitions],
        }
        if have != wanted:
            wf.update({k: v for k, v in wanted.items() if k not in ("states", "transitions")})
            wf.set("states", wanted["states"])
            wf.set("transitions", wanted["transitions"])
            wf.save()
            f._change(f"workflow {INDENT_WORKFLOW} updated")

    # in-app (bell) notifications; outgoing email is not set up yet (go-live phase)
    for name, n in NOTIFICATIONS.items():
        wanted = {"document_type": "Material Request", "event": "Value Change", "value_changed": "workflow_state",
                  "channel": "System Notification", "enabled": 1, "condition": n["condition"],
                  "subject": n["subject"], "message": n.get("message", n["subject"])}
        if not frappe.db.exists("Notification", name):
            frappe.get_doc({"doctype": "Notification", "name": name, "is_standard": 0, **wanted,
                            "recipients": n["recipients"]}).insert()
            f._change(f"notification {name}")
        else:
            doc = frappe.get_doc("Notification", name)
            have_r = [{k: r.get(k) for k in n["recipients"][0]} for r in doc.recipients]
            diff = {k: v for k, v in wanted.items() if doc.get(k) != v}
            if diff or have_r != n["recipients"]:
                doc.update(diff)
                doc.set("recipients", n["recipients"])
                doc.save()
                f._change(f"notification {name} updated")


def run():
    f._changes.clear()
    indents()
    frappe.db.commit()
    frappe.clear_cache()
    f._log(f"purchase done: {len(f._changes)} changes")
