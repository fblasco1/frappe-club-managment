frappe.ui.form.on("Grupo Actividad", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Nueva bonificación arancel"), () => {
			frappe.route_options = {
				grupo_actividad: frm.doc.name,
				actividad: frm.doc.actividad,
			};
			frappe.new_doc("Bonificacion Arancel");
		});
	},
});
