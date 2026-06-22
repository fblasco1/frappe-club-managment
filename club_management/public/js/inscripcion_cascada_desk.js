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

club_management.inscripcion_cascada.load_grupos_dialog = function (d) {
	const actividad = d.get_value("actividad");
	d.set_value("grupo", "");
	d.set_value("equipo", "");
	club_management.inscripcion_cascada._bind_equipo_query(d, null);

	if (!actividad) {
		d.toggle_display("grupo", false);
		d.toggle_display("equipo", false);
		club_management.inscripcion_cascada._bind_grupo_query(d, null);
		return;
	}

	frappe.db.get_value("Actividad", actividad, "usa_grupos", (r) => {
		const usa_grupos = cint(r?.usa_grupos);
		d.toggle_display("grupo", usa_grupos);
		d.toggle_display("equipo", usa_grupos);
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
