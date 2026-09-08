frappe.ui.form.on("Bonificacion Arancel", {
	refresh(frm) {
		frm.set_query("grupo_actividad", () => {
			if (!frm.doc.actividad) {
				return {};
			}
			return { filters: { actividad: frm.doc.actividad } };
		});
		frm.set_query("equipo_actividad", () => {
			const filters = {};
			if (frm.doc.grupo_actividad) {
				filters.grupo_actividad = frm.doc.grupo_actividad;
			} else if (frm.doc.actividad) {
				filters.actividad = frm.doc.actividad;
			}
			return { filters };
		});
	},
});
