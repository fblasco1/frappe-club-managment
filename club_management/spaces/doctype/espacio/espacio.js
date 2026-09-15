// Copyright (c) 2026, club_management and contributors
// For license information, please see license.txt

frappe.ui.form.on("Espacio", {
	refresh(frm) {
		frm.set_query("grupo_actividad", "horarios", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn] || {};
			if (!row.actividad) {
				return { filters: { name: ["in", []] } };
			}
			return { filters: { actividad: row.actividad, habilitada: 1 } };
		});
		frm.set_query("equipo_actividad", "horarios", function (doc, cdt, cdn) {
			const row = locals[cdt][cdn] || {};
			if (!row.grupo_actividad) {
				return { filters: { name: ["in", []] } };
			}
			return { filters: { grupo_actividad: row.grupo_actividad, habilitada: 1 } };
		});
	},
});

frappe.ui.form.on("Horario Entrenamiento", {
	tipo_sesion(frm, cdt, cdn) {
		_refresh_horario_titulo(cdt, cdn);
	},
	actividad(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "grupo_actividad", "");
		frappe.model.set_value(cdt, cdn, "equipo_actividad", "");
		_refresh_horario_titulo(cdt, cdn);
	},
	grupo_actividad(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "equipo_actividad", "");
		_refresh_horario_titulo(cdt, cdn);
	},
	equipo_actividad(frm, cdt, cdn) {
		_refresh_horario_titulo(cdt, cdn);
	},
});

function _refresh_horario_titulo(cdt, cdn) {
	const row = locals[cdt][cdn] || {};
	const parts = [];
	const push = (doctype, name) => {
		if (!name) {
			return Promise.resolve();
		}
		return frappe.db.get_value(doctype, name, "titulo").then((r) => {
			const titulo = (r && r.message && r.message.titulo) || name;
			parts.push(titulo);
		});
	};
	Promise.resolve()
		.then(() => push("Actividad", row.actividad))
		.then(() => push("Grupo Actividad", row.grupo_actividad))
		.then(() => push("Equipo Actividad", row.equipo_actividad))
		.then(() => {
			const cuerpo = parts.join(" / ");
			const tipo = (row.tipo_sesion || "").trim();
			let titulo = "";
			if (tipo && cuerpo) {
				titulo = `${tipo} — ${cuerpo}`;
			} else {
				titulo = tipo || cuerpo;
			}
			frappe.model.set_value(cdt, cdn, "titulo", titulo);
		});
}
