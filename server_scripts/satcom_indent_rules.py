# Satcom Indent - rules  (Server Script: DocType Event, Material Request, Before Save)
# SPEC_PHASE1 3. Source of truth is this file; satcom_p1_purchase.py writes it into ERPNext.
# Purchase indents: the Job is required unless every row is a tool (TOL); the Job goes into
# every row's Project. A rejection needs its reason.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

problems = []

if doc.material_request_type == "Purchase":
    tool_groups = frappe.get_all("Item Group", filters={"satcom_prefix": "TOL"}, pluck="name")
    all_tools = len(doc.items) > 0
    for row in doc.items:
        group = row.item_group or frappe.db.get_value("Item", row.item_code, "item_group")
        if group not in tool_groups:
            all_tools = False
    if not doc.satcom_job and not all_tools:
        problems.append("Pick the Job this indent is for. Only an indent where every row is a tool (TOL) may go without a job.")
    if doc.satcom_job:
        for row in doc.items:
            row.project = doc.satcom_job

if doc.workflow_state == "Rejected" and not (doc.satcom_rejection_reason or "").strip():
    problems.append("Enter the Rejection Reason before rejecting.")

if problems:
    frappe.throw("<br>".join(problems), title="Indent rules")
