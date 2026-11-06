// Satcom Indent  (Client Script: Material Request, Form)
// SPEC_PHASE1 3. Source of truth is this file; satcom_p1_purchase.py writes it into ERPNext.
// Reject and Cancel ask for the reason in a dialog and save it before the action runs (the
// server needs it saved: apply_workflow and cancel both reload the indent from the database).
function satcom_ask_reason(frm, title, label, fieldname, button) {
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

frappe.ui.form.on("Material Request", {
	before_workflow_action(frm) {
		if (frm.selected_workflow_action !== "Reject") return;
		frappe.dom.unfreeze();  // the workflow freezes the page before this runs
		return satcom_ask_reason(frm, __("Reject indent {0}", [frm.doc.name]), __("Rejection Reason"),
			"satcom_rejection_reason", __("Reject")).then(() => frappe.dom.freeze());
	},
	before_cancel(frm) {
		return satcom_ask_reason(frm, __("Cancel indent {0}", [frm.doc.name]), __("Cancel Reason"),
			"satcom_cancel_reason", __("Cancel indent")).catch(() => { frappe.validated = false; });
	},
});
