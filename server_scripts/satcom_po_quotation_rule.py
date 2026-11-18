# Satcom PO - quotation rule  (Server Script: DocType Event, Purchase Order, Before Submit)
# SPEC_PHASE1 4.1 (decision 27 Oct, corrected). Source of truth is this file;
# satcom_p1_purchase_orders.py writes it into ERPNext.
# Checked when the PO moves to Approved (= is submitted). A PO at or above the threshold in
# Satcom Settings needs at least "Minimum Quotations" submitted Supplier Quotations from
# different suppliers in its Quotations table, unless a Satcom Approver waived the rule with a
# reason. Under the threshold nothing is needed. The numbers live in Satcom Settings, not here.
# Amounts are compared in company currency (Rs), so a foreign-currency PO is measured in rupees.
# Sandbox: no str.format, no comprehensions over top-level names, no tuple unpacking.

threshold = float(frappe.db.get_single_value("Satcom Settings", "quotation_threshold") or 0)
needed = int(frappe.db.get_single_value("Satcom Settings", "min_quotations") or 0)
basis = frappe.db.get_single_value("Satcom Settings", "threshold_basis") or "Net total before tax"

amount = float(doc.base_net_total or 0)
if basis == "Grand total":
    amount = float(doc.base_grand_total or 0)

if amount >= threshold:
    if doc.satcom_quote_waived:
        if not (doc.satcom_waiver_reason or "").strip():
            frappe.throw("The quotation rule is waived on this PO, but the Waiver Reason is empty.",
                         title="Quotation rule")
    else:
        suppliers = []
        for q in doc.satcom_quotations:
            if not q.supplier_quotation:
                continue
            sq = frappe.db.get_value("Supplier Quotation", q.supplier_quotation, ["supplier", "docstatus"], as_dict=True)
            if sq and sq.docstatus == 1 and sq.supplier not in suppliers:
                suppliers.append(sq.supplier)
        if len(suppliers) < needed:
            frappe.throw("This PO is Rs " + str(int(amount)) + " (" + basis + "), at or above the Rs " + str(int(threshold))
                         + " limit: it needs submitted Supplier Quotations from at least " + str(needed)
                         + " different suppliers in the Quotations table, and has " + str(len(suppliers))
                         + ". Add the quotations, or a Satcom Approver ticks Quotation Rule Waived and gives the reason.",
                         title="Quotation rule")
