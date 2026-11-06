# Satcom Project - rules  (Server Script: DocType Event, Project, Before Save)
# SPEC_PHASE1 2.5. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
# Required fields per job type; the code (name = project_name) never changes once given.
# Sandbox: no str.format, no comprehensions over top-level names.

problems = []
job_type = doc.satcom_job_type

if not (doc.satcom_job_title or "").strip():
    problems.append("Job Title is required: the description of the job (the code is given on save).")

if job_type == "Customer Order":
    if not doc.customer:
        problems.append("A Customer Order job needs the Customer.")
    if not (doc.satcom_customer_po_no or "").strip():
        problems.append("A Customer Order job needs the Customer PO No.")
    if not doc.satcom_customer_po_date:
        problems.append("A Customer Order job needs the Customer PO Date.")
elif job_type == "Extension":
    if not doc.satcom_parent_job:
        problems.append("An Extension needs its Parent Job.")
    elif frappe.db.get_value("Project", doc.satcom_parent_job, "satcom_job_type") not in ("Customer Order", "Stock Build"):
        problems.append("Parent Job " + frappe.bold(doc.satcom_parent_job) + " must be a Customer Order or a Stock Build job.")
elif job_type != "Stock Build":
    problems.append("Pick the Job Type: Customer Order, Stock Build or Extension.")

if not doc.flags.in_insert:
    before = frappe.db.get_value("Project", doc.name, ["satcom_job_type", "satcom_parent_job"], as_dict=True)
    if doc.project_name != doc.name:
        problems.append("The job code " + frappe.bold(doc.name) + " can't change.")
    if before and (before.satcom_job_type != job_type or (before.satcom_parent_job or "") != (doc.satcom_parent_job or "")):
        problems.append("Job Type and Parent Job can't change once the job has its code.")

if problems:
    frappe.throw("<br>".join(problems), title="Job code rules")
