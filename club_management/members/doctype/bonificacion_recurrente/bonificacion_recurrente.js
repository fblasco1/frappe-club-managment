frappe.ui.form.on("Bonificacion Recurrente", {
	refresh(frm) {
		frm.set_query("grupo_actividad", () => {
			if (!frm.doc.actividad) {
				return {};
			}
			return { filters: { actividad: frm.doc.actividad } };
		});
	},
	actividad(frm) {
		if (frm.doc.grupo_actividad) {
			frm.set_value("grupo_actividad", null);
		}
	},
});
