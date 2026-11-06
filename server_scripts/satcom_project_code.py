# Satcom Project - job code  (Server Script: DocType Event, Project, Before Insert)
# SPEC_PHASE1 2.5. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
#
# Sets the naming series per job type, so ERPNext's own counter numbers the job:
#   Customer Order -> J-.YY.-.####   (J-26-0042)
#   Stock Build    -> S-.YY.-.####   (S-26-0007)
#   Extension      -> <parent>-.##   (J-26-0042-01, a counter per parent)
# project_name must be the code too (it is unique and mandatory), so it is filled with the code
# the series will produce; "Satcom Project - job code check" (After Insert) corrects it in the
# rare case two jobs were saved at the same moment.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

job_type = doc.satcom_job_type
yy = frappe.utils.nowdate()[2:4]  # same clock Frappe's YY uses

if job_type == "Customer Order":
    series = "J-.YY.-.####"
    prefix = "J-" + yy + "-"
    digits = 4
elif job_type == "Stock Build":
    series = "S-.YY.-.####"
    prefix = "S-" + yy + "-"
    digits = 4
elif job_type == "Extension":
    parent = (doc.satcom_parent_job or "").strip()
    if not parent:
        frappe.throw("An Extension needs its Parent Job.", title="Job code")
    parent_type = frappe.db.get_value("Project", parent, "satcom_job_type")
    if parent_type not in ("Customer Order", "Stock Build"):
        frappe.throw("Parent Job " + frappe.bold(parent) + " must be a Customer Order or a Stock Build job.",
                     title="Job code")
    series = parent + "-.##"
    prefix = parent + "-"
    digits = 2
else:
    frappe.throw("Pick the Job Type: Customer Order, Stock Build or Extension.", title="Job code")

doc.naming_series = series
rows = frappe.db.sql("select current from `tabSeries` where name = %s", (prefix,))
current = (rows[0][0] if rows else 0) or 0
doc.project_name = prefix + str(current + 1).zfill(digits)
