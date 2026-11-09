# Satcom Item - rules  (Server Script: DocType Event, Item, Before Save)
# SPEC_PHASE1 2.4. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
#
# Code format and prefix on every save (codes never change); the "required on new items" list
# only when the item is being created (Part No only in groups with "Part No required");
# MPN duplicate guard in every group; serial / batch series.

# Sandbox limits: no str.format (unsafe attribute), and no comprehensions / generator expressions
# over top-level names (they run in their own scope and can't see them).
ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
problems = []

code = doc.item_code or doc.name or ""
group = None
if doc.item_group:
    group = frappe.db.get_value("Item Group", doc.item_group, ["satcom_prefix", "satcom_code_type", "satcom_part_no_required"], as_dict=True)
prefix = group.satcom_prefix if group else None
is_new = bool(doc.flags.in_insert)

# --- code format and prefix -------------------------------------------------------------------
bad_chars = False
for c in code:
    if c not in ALLOWED:
        bad_chars = True
if not code or len(code) > 20 or bad_chars:
    problems.append("Item code " + frappe.bold(code) + " must be 1-20 characters: capital letters, digits and hyphens only.")

if not prefix:
    if is_new:
        problems.append("Item group " + frappe.bold(doc.item_group or "") + " has no code prefix. Pick one of the Satcom groups (Resistors, RF Components, Connectors, ...).")
elif group.satcom_code_type == "Specs":
    # specs groups hold one template (code = prefix) and its variants (PREFIX-<values>)
    if doc.has_variants:
        if code != prefix:
            problems.append("The " + doc.item_group + " template's code must be " + frappe.bold(prefix) + ".")
    elif doc.variant_of != prefix or not code.startswith(prefix + "-"):
        problems.append(doc.item_group + " items are made as variants: open item " + frappe.bold(prefix) + " and use Create > Single Variant.")
else:
    if not code.startswith(prefix + "-") or code == prefix + "-":
        problems.append("Item code " + frappe.bold(code) + " must start with " + frappe.bold(prefix + "-")
                        + " (group " + doc.item_group + "). Leave the code as " + frappe.bold(prefix)
                        + " to get the next number.")

# --- required on new items --------------------------------------------------------------------
if is_new:
    if not frappe.utils.strip_html(doc.description or "").strip():
        problems.append("Description is required.")
    if not doc.stock_uom:
        problems.append("Default Unit of Measure is required.")
    part_no_required = bool(group and group.satcom_part_no_required)
    has_part_no = (doc.satcom_mpn or "").strip() or (doc.satcom_drawing_no or "").strip()
    if part_no_required and not doc.has_variants and not has_part_no:
        problems.append("Enter the Manufacturer Part No or the Drawing No.")
    if bool(doc.has_serial_no) == bool(doc.has_batch_no):
        problems.append("Tick exactly one of Has Serial No (one label per piece) or Has Batch No (one label per lot), on the Inventory tab.")

if doc.inspection_required_before_purchase:
    problems.append("Inspection Required before Purchase stays off: QC inspects at release from Quality Hold.")

# --- MPN duplicate guard ----------------------------------------------------------------------
if doc.satcom_mpn:
    doc.satcom_mpn = doc.satcom_mpn.strip()
    other = frappe.db.get_value("Item", {"satcom_mpn": doc.satcom_mpn, "name": ["!=", doc.name]}, "name")
    if other:
        problems.append("Manufacturer Part No " + frappe.bold(doc.satcom_mpn) + " is already item "
                        + frappe.bold(other) + ". Use that item instead of creating a new one.")

if problems:
    frappe.throw("<br>".join(problems), title="Item code rules")

# --- incoming QC (5.2): items in Satcom groups get the starter template unless QC set another ------
if prefix and not doc.quality_inspection_template and frappe.db.exists("Quality Inspection Template", "Standard checks"):
    doc.quality_inspection_template = "Standard checks"

# --- serial / batch series (templates carry none; variants get their own) -----------------------
if not doc.has_variants:
    if doc.has_serial_no and not doc.serial_no_series:
        doc.serial_no_series = code + "-.#####"
    if doc.has_batch_no:
        if not doc.batch_number_series:
            doc.batch_number_series = code + "-B.####"
        doc.create_new_batch = 1
