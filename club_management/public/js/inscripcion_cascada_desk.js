/* global frappe */

frappe.provide("club_management.inscripcion_cascada");

club_management.inscripcion_cascada.setup_dialog_cascada = function (d) {
	d.toggle_display("grupo", false);
	d.toggle_display("equipo", false);
	club_management.inscripcion_cascada._bind_grupo_query(d, null);
	club_management.inscripcion_cascada._bind_equipo_query(d, null);
};

club_management.inscripcion_cascada._bind_grupo_query = function (d, actividad) {
	const field = d.fields_dict.grupo;
	if (!field) {
		return;
	}
	field.get_query = () => {
		if (!actividad) {
			return { filters: { name: ["in", []] } };
		}
		return { filters: { actividad, habilitada: 1 } };
	};
};

club_management.inscripcion_cascada._bind_equipo_query = function (d, grupo) {
	const field = d.fields_dict.equipo;
	if (!field) {
		return;
	}
	field.get_query = () => {
		if (!grupo) {
			return { filters: { name: ["in", []] } };
		}
		return { filters: { grupo_actividad: grupo, habilitada: 1 } };
	};
};

club_management.inscripcion_cascada._selection_from_values = function (vals) {
	if (!vals?.actividad) {
		return null;
	}
	return {
		actividad: vals.actividad,
		grupo: vals.grupo || null,
		equipo: vals.equipo || null,
	};
};

club_management.inscripcion_cascada._parse_selecciones_json = function (raw) {
	if (!raw) {
		return [];
	}
	const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
	return Array.isArray(parsed) ? parsed : [];
};

club_management.inscripcion_cascada._validate_selecciones = function (selecciones) {
	const checks = selecciones.map(
		(sel) =>
			new Promise((resolve, reject) => {
				const actividad = sel?.actividad;
				if (!actividad) {
					reject(__("Seleccione una actividad."));
					return;
				}
				frappe.db.get_value("Actividad", actividad, "usa_grupos", (r) => {
					if (cint(r?.usa_grupos) && !sel.grupo) {
						reject(
							__(
								"La actividad {0} requiere elegir un grupo / tira antes de confirmar.",
								[actividad]
							)
						);
						return;
					}
					resolve();
				});
			})
	);
	return Promise.all(checks);
};

club_management.inscripcion_cascada.collect_selecciones_dialog = function (d) {
	return new Promise((resolve, reject) => {
		const vals = d.get_values();
		if (!vals) {
			reject();
			return;
		}
		let rows = [];
		try {
			rows = club_management.inscripcion_cascada._parse_selecciones_json(vals.selecciones_json);
		} catch (e) {
			frappe.msgprint(__("Selecciones inválidas"));
			reject(e);
			return;
		}
		const pending = club_management.inscripcion_cascada._selection_from_values(vals);
		if (pending) {
			rows.push(pending);
		}
		if (!rows.length) {
			frappe.msgprint(
				__(
					"Elegí una actividad (y grupo/equipo si corresponde) y pulsá Confirmar inscripción."
				)
			);
			reject();
			return;
		}
		club_management.inscripcion_cascada
			._validate_selecciones(rows)
			.then(() => resolve(rows))
			.catch((message) => {
				frappe.msgprint(message);
				reject(message);
			});
	});
};

club_management.inscripcion_cascada.push_selection_dialog = function (d) {
	const vals = d.get_values();
	if (!vals?.actividad) {
		frappe.msgprint(__("Elegí una actividad."));
		return Promise.reject();
	}
	const pending = club_management.inscripcion_cascada._selection_from_values(vals);
	return club_management.inscripcion_cascada._validate_selecciones([pending]).then(() => {
		let rows = [];
		try {
			rows = club_management.inscripcion_cascada._parse_selecciones_json(vals.selecciones_json);
		} catch (e) {
			frappe.msgprint(__("Selecciones inválidas"));
			return Promise.reject(e);
		}
		rows.push(pending);
		d.set_value("selecciones_json", JSON.stringify(rows, null, 2));
		d.set_value("actividad", "");
		d.set_value("grupo", "");
		d.set_value("equipo", "");
		club_management.inscripcion_cascada.load_grupos_dialog(d);
		frappe.show_alert({
			message: __("Actividad agregada. Podés sumar otra o confirmar."),
			indicator: "green",
		});
	});
};

club_management.inscripcion_cascada.load_grupos_dialog = function (d) {
	const actividad = d.get_value("actividad");
	d.set_value("grupo", "");
	d.set_value("equipo", "");
	club_management.inscripcion_cascada._bind_equipo_query(d, null);

	if (!actividad) {
		d.toggle_display("grupo", false);
		d.toggle_display("equipo", false);
		d.toggle_reqd("grupo", false);
		club_management.inscripcion_cascada._bind_grupo_query(d, null);
		return;
	}

	frappe.db.get_value("Actividad", actividad, "usa_grupos", (r) => {
		const usa_grupos = cint(r?.usa_grupos);
		d.toggle_display("grupo", usa_grupos);
		d.toggle_display("equipo", usa_grupos);
		d.toggle_reqd("grupo", usa_grupos);
		club_management.inscripcion_cascada._bind_grupo_query(d, usa_grupos ? actividad : null);
		if (!usa_grupos) {
			d.set_value("grupo", "");
			d.set_value("equipo", "");
		}
	});
};

club_management.inscripcion_cascada.load_equipos_dialog = function (d) {
	const grupo = d.get_value("grupo");
	d.set_value("equipo", "");
	club_management.inscripcion_cascada._bind_equipo_query(d, grupo || null);
};

/** @deprecated use setup_dialog_cascada */
club_management.inscripcion_cascada.wire_dialog = function (d) {
	club_management.inscripcion_cascada.setup_dialog_cascada(d);
};
