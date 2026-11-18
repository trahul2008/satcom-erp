// Satcom PO  (Client Script: Purchase Order, Form)
// SPEC_PHASE1 4.1 / 4.2. Source of truth is this file; satcom_p1_purchase_orders.py writes it into ERPNext.
// Reject asks for the reason in a dialog and saves it before the action runs (the server needs
// it saved: apply_workflow reloads the PO from the database). Same dialog as on indents.
// The Quotations table offers submitted Supplier Quotations only (the rule counts only those).
function satcom_po_ask_reason(frm, title, label, fieldname, button) {
	return new Promise((resolve, reject) => {
		let done = false;
		const d = new frappe.ui.Dialog({
			title: title,
			fields: [{ fieldname: "reason", fieldtype: "Small Text", label: label, reqd: 1,
				default: frm.doc[fieldname] || "" }],
			primary_action_label: button,
			primary_action(values) {
				done = true;
				d.hide();
				frappe.db.set_value(frm.doctype, frm.doc.name, fieldname, values.reason)
					.then(() => resolve(values.reason), (e) => reject(e));
			},
		});
		d.onhide = () => { if (!done) reject(); };
		d.show();
	});
}

frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		frm.set_query("supplier_quotation", "satcom_quotations", () => ({ filters: { docstatus: 1 } }));
	},
	before_workflow_action(frm) {
		if (frm.selected_workflow_action !== "Reject") return;
		frappe.dom.unfreeze();  // the workflow freezes the page before this runs
		return satcom_po_ask_reason(frm, __("Reject purchase order {0}", [frm.doc.name]), __("Rejection Reason"),
			"satcom_rejection_reason", __("Reject")).then(() => frappe.dom.freeze());
	},
});
