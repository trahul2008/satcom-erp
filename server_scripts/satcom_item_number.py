# Satcom Item - number  (Server Script: DocType Event, Item, Before Insert)
# SPEC_PHASE1 2.4. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
#
# Number groups: when the code is blank or just the group prefix ("RFC"), give the next free
# <PREFIX>-NNNN. "Next free" = highest four-digit number among existing items AND deleted items
# with that prefix, plus one, so codes are never reused. Only codes of the exact form PREFIX-NNNN
# count (variants and anything else are ignored). The sandbox has no `re`, so the match is a
# MariaDB REGEXP in a read-only query.

group = None
if doc.item_group:
    group = frappe.db.get_value("Item Group", doc.item_group, ["satcom_prefix", "satcom_code_type"], as_dict=True)

code = (doc.item_code or "").strip().upper()

if group and group.satcom_prefix and group.satcom_code_type == "Number" and not doc.variant_of \
        and code in ("", group.satcom_prefix):
    prefix = group.satcom_prefix
    rows = frappe.db.sql(
        """select max(n) from (
            select cast(substring(name, %(start)s) as unsigned) as n
              from `tabItem` where name regexp %(pattern)s
            union all
            select cast(substring(deleted_name, %(start)s) as unsigned) as n
              from `tabDeleted Document`
             where deleted_doctype = 'Item' and deleted_name regexp %(pattern)s
        ) t""",
        {"start": len(prefix) + 2, "pattern": "^" + prefix + "-[0-9]{4}$"},
    )
    last = (rows[0][0] if rows else None) or 0
    if last >= 9999:
        frappe.throw("All numbers for " + prefix + " are used (up to " + prefix + "-9999).", title="Item code")
    new_code = prefix + "-" + str(last + 1).zfill(4)
    # the form copies the code into an empty item name; don't leave the bare prefix there
    if (doc.item_name or "").strip().upper() in ("", code):
        doc.item_name = new_code
    doc.item_code = new_code
