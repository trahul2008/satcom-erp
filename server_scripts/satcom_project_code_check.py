# Satcom Project - job code check  (Server Script: DocType Event, Project, After Insert)
# SPEC_PHASE1 2.5. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
# project_name = the job code. Before Insert predicts it; if another job took that number at the
# same moment, put the real code in.

if doc.project_name != doc.name:
    frappe.db.set_value("Project", doc.name, "project_name", doc.name)
    doc.project_name = doc.name
