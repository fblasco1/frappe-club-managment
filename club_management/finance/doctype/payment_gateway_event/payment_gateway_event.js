frappe.ui.form.on("Payment Gateway Event", {
	refresh(frm) {
		frm.disable_save();
	},
});
