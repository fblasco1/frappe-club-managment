frappe.ui.form.on("Payment Log", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		[
			"gateway_transaction_id",
			"provider",
			"gateway_reference",
			"sales_invoice",
			"payment_entry",
			"socio",
			"payload_json",
			"received_at",
		].forEach((fieldname) => {
			frm.set_df_property(fieldname, "read_only", 1);
		});
	},
});
