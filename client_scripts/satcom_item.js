// Satcom Item  (Client Script: Item, Form)
// SPEC_PHASE1 2.4. Source of truth is this file; satcom_p1_foundation.py writes it into ERPNext.
// On a new item, picking a number-coded group puts its prefix in Item Code ("RFC"); the server
// replaces it with the next free number on save. Cables and Wire default to the Meter UOM.
frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.is_new() && !frm.doc.variant_of) {
			frm.set_df_property("item_code", "description",
				__("Pick the Item Group first. For numbered groups leave the 3-letter prefix: the number is given when you save."));
		}
	},
	item_group(frm) {
		if (!frm.is_new() || frm.doc.variant_of || !frm.doc.item_group) return;
		frappe.db.get_value("Item Group", frm.doc.item_group, ["satcom_prefix", "satcom_code_type"]).then((r) => {
			const g = r.message || {};
			const code = (frm.doc.item_code || "").trim().toUpperCase();
			const bare = !code || /^[A-Z]{3}$/.test(code);  // empty, or another group's prefix
			if (g.satcom_code_type === "Number" && bare) {
				frm.set_value("item_code", g.satcom_prefix);
			}
			if (g.satcom_code_type === "Specs") {
				frappe.show_alert({
					message: __("{0} items are variants: open item {1} and use Create > Single Variant.", [frm.doc.item_group, g.satcom_prefix]),
					indicator: "orange",
				});
			}
			if (g.satcom_prefix === "CBL") {
				frm.set_value("stock_uom", "Meter");
			}
		});
	},
});
