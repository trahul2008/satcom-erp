"""Phase 1 quotations and purchase orders for satcom-erp (SPEC_PHASE1.md section 4). Idempotent.

Run after satcom_p1_foundation.run, satcom_p1_purchase.run and satcom_p1_receipt_qc.run (copy
server_scripts, client_scripts, print_formats and assets to /tmp/satcom_scripts first):
    bench --site frontend execute erpnext.satcom_p1_purchase_orders.run
Prints only what it changed; a second run reports "0 changes".
Last step: Buying Settings "Purchase Order Required" goes to Yes (spec 5.1: once section 4 is
live a GRN must come from a PO), so the interim "GRN without a PO" ends with this run.
"""
import hashlib

import frappe

from erpnext import satcom_p1_foundation as f

COMPANY = f.COMPANY

# 4.1 Satcom Settings (single) ---------------------------------------------------------------

SETTINGS = "Satcom Settings"
THRESHOLD_BASES = ["Net total before tax", "Grand total"]
# OPEN items (spec section 11) are settings with the spec's default; management changes them here
SETTINGS_FIELDS = [
    {"fieldname": "purchase_section", "label": "Quotation Rule for Purchase Orders", "fieldtype": "Section Break"},
    {"fieldname": "quotation_threshold", "label": "Quotation Threshold (Rs)", "fieldtype": "Currency",
     "default": "300000",
     "description": "A purchase order at or above this amount needs supplier quotations before it is approved"},
    {"fieldname": "min_quotations", "label": "Minimum Quotations", "fieldtype": "Int", "default": "3",
     "description": "How many Supplier Quotations, each from a different supplier, such a PO needs"},
    {"fieldname": "threshold_basis", "label": "Threshold Basis", "fieldtype": "Select",
     "options": "\n".join(THRESHOLD_BASES), "default": THRESHOLD_BASES[0],
     "description": "Which PO amount is compared with the threshold"},
    {"fieldname": "stores_section", "label": "Rejected Material", "fieldtype": "Section Break"},
    {"fieldname": "concession_needs_approver", "label": "Concession Needs Approver", "fieldtype": "Check",
     "description": "On: Use under Concession needs Concession Approved By, set by a Satcom Approver. "
                    "Off: stores decides."},
]
# stored once, when the field has no value yet; a value management has set is never overwritten
SETTINGS_DEFAULTS = {"quotation_threshold": 300000, "min_quotations": 3, "threshold_basis": THRESHOLD_BASES[0],
                     "concession_needs_approver": 0}

# 4.1 quotations linked on the PO -------------------------------------------------------------

PO_QUOTATION = "Satcom PO Quotation"
PO_QUOTATION_FIELDS = [
    {"fieldname": "supplier_quotation", "label": "Supplier Quotation", "fieldtype": "Link",
     "options": "Supplier Quotation", "reqd": 1, "in_list_view": 1, "columns": 5},
    {"fieldname": "supplier", "label": "Supplier", "fieldtype": "Link", "options": "Supplier", "read_only": 1,
     "fetch_from": "supplier_quotation.supplier", "in_list_view": 1, "columns": 5},
]

# 4.2 PO approval -----------------------------------------------------------------------------

PO_WORKFLOW = "Satcom PO Approval"
# state -> (doc_status, role that may edit in this state, indicator style). Purchase and the
# indenters both raise POs; both profiles hold Purchase User, so that role stands for "Purchase
# or Indenter" (one transition: Frappe would show a second one as a duplicate button).
PO_STATES = {
    "Draft": ("0", "Purchase User", ""),
    "Pending Approval": ("0", "Satcom Approver", "Warning"),
    "Approved": ("1", "Satcom Approver", "Success"),
    "Rejected": ("0", "Satcom Approver", "Danger"),
}
# (state, action, next state, allowed role, allow self approval). Every PO needs approval.
PO_TRANSITIONS = [
    ("Draft", "Submit for Approval", "Pending Approval", "Purchase User", 1),
    ("Pending Approval", "Approve", "Approved", "Satcom Approver", 0),
    ("Pending Approval", "Reject", "Rejected", "Satcom Approver", 1),
]

# 4.2 letterhead, addresses, company details (from the warranty certificate footer) -----------

LETTERHEAD = "Satcom Technologies"
LOGO_FILE = "satcom-logo.png"  # assets/satcom-logo.png: scan crop, replace with the original when Rahul has it
CIN = "U32204TG1999PTC033193"
GSTIN = "36AAECS9513M1ZW"
PHONE, FAX = "+91-40-2371 0333", "+91-40-2371 3444"
EMAIL, WEBSITE = "info@satcomindia.in", "www.satcomindia.in"
REGISTERED_OFFICE = "403, Bhanu Enclave, 7-1-638/1, Sunder Nagar, Erragadda, Hyderabad - 500 038"
FACTORY = "Plot No 12, EMC-TGIIC, Maheshwaram, Rangareddy District, Telangana 501 359"
# address title -> fields. Registered office = billing, factory = shipping (POs deliver there).
REGISTERED_TITLE, FACTORY_TITLE = "Satcom Technologies Registered Office", "Satcom Technologies Factory"
ADDRESSES = {
    REGISTERED_TITLE: {
        "address_type": "Billing", "address_line1": "403, Bhanu Enclave, 7-1-638/1",
        "address_line2": "Sunder Nagar, Erragadda", "city": "Hyderabad", "state": "Telangana",
        "pincode": "500038", "country": "India", "phone": PHONE, "fax": FAX, "email_id": EMAIL,
        "is_primary_address": 1, "is_shipping_address": 0,
    },
    FACTORY_TITLE: {
        "address_type": "Shipping", "address_line1": "Plot No 12, EMC-TGIIC", "city": "Maheshwaram", "county": "Rangareddy District", "state": "Telangana", "pincode": "501359",
        "country": "India", "is_primary_address": 0, "is_shipping_address": 1,
    },
}
LETTERHEAD_HTML = """<table style="width: 100%; border-bottom: 1px solid #000; margin-bottom: 8px;">
<tr>
<td style="width: 28%; vertical-align: middle; padding-bottom: 6px;"><img src="{logo}" alt="Satcom" style="max-height: 70px; max-width: 100%;"></td>
<td style="width: 72%; vertical-align: middle; text-align: right; font-size: 9pt; line-height: 1.35; padding-bottom: 6px;">
<div style="font-size: 14pt; font-weight: bold;">{company}</div>
<div><b>Registered office:</b> {registered}</div>
<div>Ph: {phone}, Fax: {fax}, {email}, {website}</div>
<div><b>Factory:</b> {factory}</div>
<div>CIN: {cin} &middot; GSTIN: {gstin}</div>
</td>
</tr>
</table>"""

PO_FORMAT = "Satcom PO"


def _ensure(doctype, name, values):
    if not frappe.db.exists(doctype, name):
        frappe.get_doc({"doctype": doctype, **values}).insert()
        f._change(f"{doctype} {name}")


def _doctype(name, fields, **props):
    """Create or update one custom DocType (custom=1: it lives in the database, no files).
    Fields are compared one by one; permissions are written only when the DocType is created."""
    if not frappe.db.exists("DocType", name):
        frappe.get_doc({"doctype": "DocType", "name": name, "custom": 1, "fields": fields, **props}).insert()
        f._change(f"doctype {name}")
        return
    doc = frappe.get_doc("DocType", name)
    changed = []
    for prop, value in props.items():
        if prop != "permissions" and (doc.get(prop) or None) != (value or None):
            doc.set(prop, value)
            changed.append(prop)
    have = {d.fieldname: d for d in doc.fields}
    for wanted in fields:
        df = have.get(wanted["fieldname"])
        if not df:
            doc.append("fields", wanted)
            changed.append(wanted["fieldname"])
            continue
        diff = {k: v for k, v in wanted.items() if (df.get(k) or None) != (v or None)}
        if diff:
            df.update(diff)
            changed.append(f"{wanted['fieldname']} {sorted(diff)}")
    if changed:
        doc.save()
        f._change(f"doctype {name}: {', '.join(changed)}")


def satcom_settings():
    _doctype(SETTINGS, SETTINGS_FIELDS, module="Buying", issingle=1,
             description="Satcom's own rules that management may change (SPEC_PHASE1 4.1, 5.3, 11)",
             permissions=[{"role": "System Manager", "read": 1, "write": 1, "create": 1}])
    stored = frappe.db.get_singles_dict(SETTINGS)
    for field, value in SETTINGS_DEFAULTS.items():
        if field not in stored:
            frappe.db.set_single_value(SETTINGS, field, value)
            f._change(f"{SETTINGS}: {field} = {value!r} (spec default)")


def quotations():
    _doctype(PO_QUOTATION, PO_QUOTATION_FIELDS, module="Buying", istable=1, editable_grid=1,
             description="One Supplier Quotation compared for a Purchase Order (SPEC_PHASE1 4.1)")
    f._custom_field("Purchase Order", "satcom_quotation_section", label="Quotations", fieldtype="Section Break",
                    insert_after="net_total")
    f._custom_field("Purchase Order", "satcom_quotations", label="Supplier Quotations Compared", fieldtype="Table",
                    options=PO_QUOTATION, insert_after="satcom_quotation_section",
                    description="A PO at or above the threshold in Satcom Settings needs quotations from "
                                "different suppliers here before it is approved. Smaller POs need none.")
    f._custom_field("Purchase Order", "satcom_quote_waived", label="Quotation Rule Waived", fieldtype="Check",
                    insert_after="satcom_quotations", no_copy=1,
                    description="Only a Satcom Approver may tick this; the Waiver Reason is required")
    f._custom_field("Purchase Order", "satcom_waiver_reason", label="Waiver Reason", fieldtype="Small Text",
                    insert_after="satcom_quote_waived", no_copy=1, depends_on="eval:doc.satcom_quote_waived",
                    mandatory_depends_on="eval:doc.satcom_quote_waived")


def _workflow(name, document_type, states, transitions):
    for state, (_, _, style) in states.items():
        _ensure("Workflow State", state, {"workflow_state_name": state, "style": style})
    for _, action, _, _, _ in transitions:
        _ensure("Workflow Action Master", action, {"workflow_action_name": action})
    wanted = {
        "document_type": document_type, "is_active": 1, "send_email_alert": 0, "override_status": 0,
        "workflow_state_field": "workflow_state",
        "states": [{"state": s, "doc_status": d, "allow_edit": r} for s, (d, r, _) in states.items()],
        "transitions": [{"state": s, "action": a, "next_state": n, "allowed": r, "allow_self_approval": self_ok}
                        for s, a, n, r, self_ok in transitions],
    }
    if not frappe.db.exists("Workflow", name):
        frappe.get_doc({"doctype": "Workflow", "workflow_name": name, **wanted}).insert()
        f._change(f"workflow {name}")
        return
    wf = frappe.get_doc("Workflow", name)
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
        f._change(f"workflow {name} updated")


def approval():
    f._custom_field("Purchase Order", "satcom_rejection_reason", label="Rejection Reason", fieldtype="Small Text",
                    insert_after="schedule_date", no_copy=1,
                    depends_on='eval:["Pending Approval", "Rejected"].includes(doc.workflow_state)',
                    description="Asked for when an approver clicks Reject")
    f._server_script("Satcom PO - rules", "Purchase Order", "Before Save", "satcom_po_rules.py")
    f._server_script("Satcom PO - approval guard", "Purchase Order", "Before Submit", "satcom_po_approval_guard.py")
    f._server_script("Satcom PO - quotation rule", "Purchase Order", "Before Submit", "satcom_po_quotation_rule.py")
    f._client_script("Satcom PO", "Purchase Order", "satcom_po.js")
    _workflow(PO_WORKFLOW, "Purchase Order", PO_STATES, PO_TRANSITIONS)


def _logo_url():
    """The public File holding assets/satcom-logo.png; a new File when the logo file changes."""
    with open(f"{f.SCRIPTS_DIR}/assets/{LOGO_FILE}", "rb") as fh:
        content = fh.read()
    content_hash = hashlib.md5(content, usedforsecurity=False).hexdigest()  # as Frappe's File does
    url = frappe.db.get_value("File", {"content_hash": content_hash, "is_private": 0}, "file_url")
    if not url:
        url = frappe.get_doc({"doctype": "File", "file_name": LOGO_FILE, "content": content,
                              "is_private": 0}).insert().file_url
        f._change(f"file {url} (letterhead logo)")
    return url


def _address(title, values):
    name = frappe.db.get_value("Address", {"address_title": title, "address_type": values["address_type"]})
    link = {"link_doctype": "Company", "link_name": COMPANY}
    if not name:
        frappe.get_doc({"doctype": "Address", "address_title": title, **values, "links": [link]}).insert()
        f._change(f"address {title} ({values['address_type']})")
        return
    f._set_values("Address", name, {"disabled": 0, **values})
    if not frappe.db.exists("Dynamic Link", {"parenttype": "Address", "parent": name, **link}):
        doc = frappe.get_doc("Address", name)
        doc.append("links", link)
        doc.save()
        f._change(f"address {title}: linked to {COMPANY}")


def letterhead():
    # CIN has no standard Company field; GSTIN is the Tax ID (India Compliance is not installed)
    f._custom_field("Company", "satcom_cin", label="CIN", fieldtype="Data", insert_after="tax_id",
                    description="Corporate Identification Number, printed on the letterhead")
    have = frappe.db.get_value("Company", COMPANY, ["tax_id", "satcom_cin"], as_dict=True)
    for field, value in (("tax_id", GSTIN), ("satcom_cin", CIN)):
        if have.get(field) and have.get(field) != value:
            frappe.throw(f"Company {field} is {have.get(field)!r}, the spec says {value!r}: ask Rahul which is right")

    html = LETTERHEAD_HTML.format(logo=_logo_url(), company=COMPANY, registered=REGISTERED_OFFICE, phone=PHONE,
                                  fax=FAX, email=EMAIL, website=WEBSITE, factory=FACTORY, cin=CIN, gstin=GSTIN)
    wanted = {"source": "HTML", "content": html, "is_default": 1, "disabled": 0}
    if not frappe.db.exists("Letter Head", LETTERHEAD):
        frappe.get_doc({"doctype": "Letter Head", "letter_head_name": LETTERHEAD, **wanted}).insert()
        f._change(f"letter head {LETTERHEAD} (default)")
    else:
        f._set_values("Letter Head", LETTERHEAD, wanted)  # saving it as default unsets the old default

    f._set_values("Company", COMPANY, {"tax_id": GSTIN, "satcom_cin": CIN, "default_letter_head": LETTERHEAD})
    for title, values in ADDRESSES.items():
        _address(title, values)


def print_format():
    wanted = {"doc_type": "Purchase Order", "standard": "No", "custom_format": 1, "print_format_type": "Jinja",
              "html": f._source("print_formats", "satcom_po.html"), "disabled": 0}
    if not frappe.db.exists("Print Format", PO_FORMAT):
        frappe.get_doc({"doctype": "Print Format", "name": PO_FORMAT, **wanted}).insert()
        f._change(f"print format {PO_FORMAT}")
    else:
        f._set_values("Print Format", PO_FORMAT, wanted)
    f._doctype_property("Purchase Order", "default_print_format", PO_FORMAT, "Data")


def go_live():
    # 5.1: section 4 is live, so a GRN must come from a PO (the interim of 6 Nov ends)
    f._set_values("Buying Settings", None, {"po_required": "Yes"})


def run():
    f._changes.clear()
    satcom_settings()
    quotations()
    approval()
    letterhead()
    print_format()
    go_live()
    frappe.db.commit()
    frappe.clear_cache()
    f._log(f"purchase-orders done: {len(f._changes)} changes")
