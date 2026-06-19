/* global frappe */

frappe.ui.form.on("Inscripcion Actividad", {
	refresh(frm) {
		frm.set_query("actividad", () => ({
			filters: { habilitada: 1 },
		}));
		club_inscripcion_apply_queries(frm);
		club_inscripcion_toggle_grupo_equipo(frm);
	},

	actividad(frm) {
		frm.set_value("grupo_actividad", "");
		frm.set_value("equipo_actividad", "");
		club_inscripcion_apply_queries(frm);
		club_inscripcion_toggle_grupo_equipo(frm);
	},

	grupo_actividad(frm) {
		frm.set_value("equipo_actividad", "");
		club_inscripcion_apply_queries(frm);
	},
});

function club_inscripcion_apply_queries(frm) {
	frm.set_query("grupo_actividad", () => {
		if (!frm.doc.actividad) {
			return { filters: { name: ["in", []] } };
		}
		return {
			filters: {
				actividad: frm.doc.actividad,
				habilitada: 1,
			},
		};
	});

	frm.set_query("equipo_actividad", () => {
		if (!frm.doc.grupo_actividad) {
			return { filters: { name: ["in", []] } };
		}
		return {
			filters: {
				grupo_actividad: frm.doc.grupo_actividad,
				habilitada: 1,
			},
		};
	});
}

function club_inscripcion_toggle_grupo_equipo(frm) {
	if (!frm.doc.actividad) {
		frm.toggle_display("grupo_actividad", false);
		frm.toggle_display("equipo_actividad", false);
		frm.toggle_reqd("grupo_actividad", false);
		return;
	}

	frappe.db.get_value("Actividad", frm.doc.actividad, "usa_grupos", (r) => {
		const usa_grupos = cint(r?.usa_grupos);
		frm.toggle_display("grupo_actividad", usa_grupos);
		frm.toggle_display("equipo_actividad", usa_grupos);
		frm.toggle_reqd("grupo_actividad", usa_grupos);
	});
}
