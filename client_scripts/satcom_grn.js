// Satcom GRN  (Client Script: Purchase Receipt, Form)
// SPEC_PHASE1 5.1. Source of truth is this file; satcom_p1_receipt_qc.py writes it into ERPNext.
// A new receipt puts everything in Quality Hold (the server enforces it; this just fills it in).
const SATCOM_QH = "Quality Hold - STPL";
frappe.ui.form.on("Purchase Receipt", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.is_return && frm.doc.set_warehouse !== SATCOM_QH) {
			frm.set_value("set_warehouse", SATCOM_QH);
		}
	},
});
frappe.ui.form.on("Purchase Receipt Item", {
	items_add(frm, cdt, cdn) {
		if (!frm.doc.is_return) frappe.model.set_value(cdt, cdn, "warehouse", SATCOM_QH);
	},
});
