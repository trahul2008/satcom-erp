"""Phase 1 foundation for satcom-erp (SPEC_PHASE1.md section 2). Idempotent.

Run (after satcom_demo_cleanup.run):
    bench --site frontend execute erpnext.satcom_p1_foundation.run
Each step compares before it writes and prints only what it changed, so a second run reports
"0 changes". Built so far: 2.1 settings, 2.2 roles and demo users.
"""
import frappe

COMPANY = "Satcom Technologies Pvt Ltd"

_changes = []


def _log(msg):
    print(f"[p1-foundation] {msg}")


def _set_values(doctype, name, values):
    """Set fields on one record (name=None for a single doctype), saving only if something differs."""
    doc = frappe.get_single(doctype) if name is None else frappe.get_doc(doctype, name)
    diff = {f: v for f, v in values.items() if doc.get(f) != v}
    if not diff:
        return
    for field, value in diff.items():
        if not doc.meta.has_field(field):
            frappe.throw(f"{doctype} has no field {field} in this version")
        _changes.append(f"{doctype}{' ' + name if name else ''}: {field} {doc.get(field)!r} -> {value!r}")
        _log(_changes[-1])
        doc.set(field, value)
    doc.save()


# 2.1 Settings -------------------------------------------------------------------------------

def settings():
    # Perpetual inventory off, so stock never posts GL entries (accounts stay in Tally).
    _set_values("Company", COMPANY, {"enable_perpetual_inventory": 0})
    active_gl = frappe.db.count("GL Entry", {"is_cancelled": 0})
    if active_gl:
        frappe.throw(f"{active_gl} active GL entries exist; accounts must stay in Tally")
    # Valuation stays FIFO (OPEN, spec section 11): checked, never changed here.
    valuation = frappe.db.get_single_value("Stock Settings", "valuation_method")
    if valuation != "FIFO":
        frappe.throw(f"Stock Settings valuation method is {valuation}, spec keeps FIFO (open item)")
    _set_values("Buying Settings", None, {
        "supp_master_name": "Supplier Name",
        "po_required": "No",
        "pr_required": "No",
        "maintain_same_rate": 0,  # POs must allow the approved quotation's rate
    })


# 2.2 Roles ----------------------------------------------------------------------------------

CUSTOM_ROLES = ["Satcom Approver", "Satcom Indenter"]
# Satcom role (one Role Profile each; a user may hold several) -> ERPNext roles. Accounts: phase 3.
ROLE_PROFILES = {
    "Satcom Approver": ["Satcom Approver", "Purchase Manager", "Stock User"],
    "Satcom Indenter": ["Satcom Indenter", "Projects User", "Purchase User"],
    "Satcom Purchase": ["Purchase User"],
    "Satcom Stores": ["Stock User", "Item Manager"],
    "Satcom QC": ["Quality Manager", "Stock User"],
}
# Test users for the workflows (spec 2.2): no password, so they can't sign in until one is set.
DEMO_USERS = {
    "demo.approver1@example.com": ("Demo Approver 1", ["Satcom Approver"]),
    "demo.approver2@example.com": ("Demo Approver 2", ["Satcom Approver"]),
    "demo.indenter@example.com": ("Demo Indenter", ["Satcom Indenter", "Satcom Purchase"]),
    "demo.stores@example.com": ("Demo Stores", ["Satcom Stores", "Satcom QC"]),
    "demo.allroles@example.com": ("Demo All Roles", list(ROLE_PROFILES)),
}


def _change(msg):
    _changes.append(msg)
    _log(msg)


def roles():
    for name in CUSTOM_ROLES:
        if not frappe.db.exists("Role", name):
            frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1, "is_custom": 1}).insert()
            _change(f"role {name}")
        else:
            _set_values("Role", name, {"desk_access": 1, "disabled": 0})

    for profile, wanted in ROLE_PROFILES.items():
        if not frappe.db.exists("Role Profile", profile):
            frappe.get_doc({"doctype": "Role Profile", "role_profile": profile,
                            "roles": [{"role": r} for r in wanted]}).insert()
            _change(f"role profile {profile}: {', '.join(wanted)}")
            continue
        doc = frappe.get_doc("Role Profile", profile)
        have = sorted(r.role for r in doc.roles)
        if have != sorted(wanted):
            doc.set("roles", [{"role": r} for r in wanted])
            doc.save()  # Frappe pushes the new roles to every user holding the profile
            _change(f"role profile {profile}: {have} -> {sorted(wanted)}")

    for email, (full_name, profiles) in DEMO_USERS.items():
        if not frappe.db.exists("User", email):
            first, _, last = full_name.partition(" ")
            frappe.get_doc({
                "doctype": "User", "email": email, "first_name": first, "last_name": last,
                "user_type": "System User", "enabled": 1, "send_welcome_email": 0,
                "role_profiles": [{"role_profile": p} for p in profiles],
            }).insert()
            _change(f"user {email}: {', '.join(profiles)}")
            continue
        user = frappe.get_doc("User", email)
        have = sorted(p.role_profile for p in user.role_profiles)
        if have != sorted(profiles) or not user.enabled:
            user.enabled = 1
            user.set("role_profiles", [{"role_profile": p} for p in profiles])
            user.save()
            _change(f"user {email}: {have} -> {sorted(profiles)}")


def run():
    _changes.clear()
    settings()
    roles()
    frappe.db.commit()
    frappe.clear_cache()
    _log(f"done: {len(_changes)} changes")
