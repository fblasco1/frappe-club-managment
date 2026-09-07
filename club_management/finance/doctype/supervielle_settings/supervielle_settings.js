frappe.ui.form.on("Supervielle Settings", {
	refresh(frm) {
		if (cint(frm.doc.sandbox_mode)) {
			frm.dashboard.set_headline(
				__("Sandbox activo: las publicaciones van a Cobranza Ágil de test. No usar socios reales.")
			);
		}
	},
});
