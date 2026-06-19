/* global frappe */
frappe.provide("club_management_socio_alta_guiada");

club_management_socio_alta_guiada.FLUJO_OPCIONES = [
	"Activar ahora (recomendado)",
	"Pendiente de inscripción (sin pago online)",
	"Pendiente de pago",
];

club_management_socio_alta_guiada.open = function (frm) {
	const prefill = frm ? club_management_socio_alta_guiada._collect_from_frm(frm) : {};
	const d = new frappe.ui.Dialog({
		title: __("Alta guiada de socio"),
		size: "large",
		fields: [
			{ fieldtype: "Section Break", label: __("Datos personales") },
			{
				fieldname: "nombre",
				fieldtype: "Data",
				label: __("Nombre"),
				reqd: 1,
				default: prefill.nombre,
			},
			{
				fieldname: "apellido",
				fieldtype: "Data",
				label: __("Apellido"),
				reqd: 1,
				default: prefill.apellido,
			},
			{
				fieldname: "dni",
				fieldtype: "Data",
				label: __("DNI"),
				reqd: 1,
				default: prefill.dni,
			},
			{
				fieldname: "nacionalidad",
				fieldtype: "Link",
				label: __("Nacionalidad"),
				options: "Country",
				reqd: 1,
				default: prefill.nacionalidad || "Argentina",
			},
			{
				fieldname: "fecha_nacimiento",
				fieldtype: "Date",
				label: __("Fecha de nacimiento"),
				reqd: 1,
				default: prefill.fecha_nacimiento,
				onchange: () => club_management_socio_alta_guiada._sugerir_categoria(d),
			},
			{
				fieldname: "genero",
				fieldtype: "Select",
				label: __("Género"),
				options: "\nMasculino\nFemenino\nOtro\nPrefiero no decir",
				reqd: 1,
				default: prefill.genero,
			},
			{
				fieldname: "email",
				fieldtype: "Data",
				label: __("Email"),
				options: "Email",
				reqd: 1,
				default: prefill.email,
			},
			{
				fieldname: "telefono_fijo",
				fieldtype: "Data",
				label: __("Teléfono fijo"),
				default: prefill.telefono_fijo,
			},
			{
				fieldname: "telefono_movil",
				fieldtype: "Data",
				label: __("Teléfono móvil"),
				reqd: 1,
				default: prefill.telefono_movil,
			},
			{ fieldtype: "Section Break", label: __("Domicilio") },
			{
				fieldname: "calle",
				fieldtype: "Data",
				label: __("Calle"),
				default: prefill.calle,
			},
			{
				fieldname: "numero",
				fieldtype: "Data",
				label: __("Número"),
				default: prefill.numero,
			},
			{
				fieldname: "piso",
				fieldtype: "Data",
				label: __("Piso"),
				default: prefill.piso,
			},
			{
				fieldname: "departamento",
				fieldtype: "Data",
				label: __("Departamento"),
				default: prefill.departamento,
			},
			{
				fieldname: "provincia",
				fieldtype: "Data",
				label: __("Provincia"),
				default: prefill.provincia,
			},
			{
				fieldname: "ciudad",
				fieldtype: "Data",
				label: __("Ciudad"),
				default: prefill.ciudad,
			},
			{
				fieldname: "localidad_barrio",
				fieldtype: "Data",
				label: __("Localidad / Barrio"),
				default: prefill.localidad_barrio,
			},
			{
				fieldname: "codigo_postal",
				fieldtype: "Data",
				label: __("Código postal"),
				default: prefill.codigo_postal,
			},
			{ fieldtype: "Section Break", label: __("Categoría y vínculos") },
			{
				fieldname: "categoria",
				fieldtype: "Select",
				label: __("Categoría"),
				options: "\nActivo\nMenor\n2° Hermano\n3° Hermano\nAdherente\nJubilado\nVitalicio",
				reqd: 1,
				default: prefill.categoria || "Activo",
			},
			{
				fieldname: "tipo_tutor",
				fieldtype: "Select",
				label: __("Tipo de tutor"),
				options: "\nSocio\nTutor No Socio",
				depends_on: "eval:doc.categoria=='Menor'",
				default: prefill.tipo_tutor,
			},
			{
				fieldname: "tutor_socio",
				fieldtype: "Link",
				label: __("Tutor (socio)"),
				options: "Socio",
				depends_on: "eval:doc.categoria=='Menor' && doc.tipo_tutor=='Socio'",
				default: prefill.tipo_tutor === "Socio" ? prefill.tutor : "",
			},
			{
				fieldname: "tutor_no_socio",
				fieldtype: "Link",
				label: __("Tutor (no socio)"),
				options: "Tutor No Socio",
				depends_on: "eval:doc.categoria=='Menor' && doc.tipo_tutor=='Tutor No Socio'",
				default: prefill.tipo_tutor === "Tutor No Socio" ? prefill.tutor : "",
			},
			{ fieldtype: "Section Break", label: __("Después del alta") },
			{
				fieldname: "flujo_destino",
				fieldtype: "Select",
				label: __("Destino"),
				options: club_management_socio_alta_guiada.FLUJO_OPCIONES.join("\n"),
				default: "Activar ahora (recomendado)",
				description: __(
					"Activar ahora deja al socio operativo. Pendiente de inscripción salta el cobro online y permite inscribir actividades."
				),
			},
			{ fieldtype: "Section Break", label: __("Inscripción (opcional)") },
			{
				fieldname: "inscribir_actividad",
				fieldtype: "Check",
				label: __("Inscribir en actividad al guardar"),
			},
			{
				fieldname: "actividad",
				fieldtype: "Link",
				label: __("Actividad"),
				options: "Actividad",
				depends_on: "eval:doc.inscribir_actividad",
				get_query: () => ({ filters: { habilitada: 1 } }),
				onchange: () => club_management.inscripcion_cascada.load_grupos_dialog(d),
			},
			{
				fieldname: "grupo",
				fieldtype: "Link",
				label: __("Grupo / tira"),
				options: "Grupo Actividad",
				depends_on: "eval:doc.inscribir_actividad",
				onchange: () => club_management.inscripcion_cascada.load_equipos_dialog(d),
			},
			{
				fieldname: "equipo",
				fieldtype: "Link",
				label: __("Equipo / categoría"),
				options: "Equipo Actividad",
				depends_on: "eval:doc.inscribir_actividad",
			},
		],
		primary_action_label: __("Crear socio"),
		primary_action(values) {
			club_management_socio_alta_guiada._crear_socio(d, values, frm);
		},
	});
	d.show();
	club_management.inscripcion_cascada.setup_dialog_cascada(d);
	if (prefill.fecha_nacimiento) {
		club_management_socio_alta_guiada._sugerir_categoria(d);
	}
};

club_management_socio_alta_guiada._collect_from_frm = function (frm) {
	const campos = [
		"nombre",
		"apellido",
		"dni",
		"nacionalidad",
		"fecha_nacimiento",
		"genero",
		"email",
		"telefono_fijo",
		"telefono_movil",
		"calle",
		"numero",
		"piso",
		"departamento",
		"provincia",
		"ciudad",
		"localidad_barrio",
		"codigo_postal",
		"categoria",
		"tipo_tutor",
		"tutor",
	];
	const out = {};
	for (const fieldname of campos) {
		if (frm.doc[fieldname]) {
			out[fieldname] = frm.doc[fieldname];
		}
	}
	return out;
};

club_management_socio_alta_guiada._sugerir_categoria = function (d) {
	const fecha = d.get_value("fecha_nacimiento");
	if (!fecha) {
		return;
	}
	frappe.call({
		method: "club_management.members.api.socio_operaciones_desk.sugerir_categoria_desk",
		args: { fecha_nacimiento: fecha },
		callback(r) {
			if (r.message?.categoria) {
				d.set_value("categoria", r.message.categoria);
			}
		},
	});
};

club_management_socio_alta_guiada._load_grupos = function (d) {
	club_management.inscripcion_cascada.load_grupos_dialog(d);
};

club_management_socio_alta_guiada._load_equipos = function (d) {
	club_management.inscripcion_cascada.load_equipos_dialog(d);
};

club_management_socio_alta_guiada._map_flujo = function (flujo) {
	if (flujo === "Activar ahora (recomendado)") {
		return { activar_al_guardar: 1, omitir_pago_al_guardar: 0 };
	}
	if (flujo === "Pendiente de inscripción (sin pago online)") {
		return { activar_al_guardar: 0, omitir_pago_al_guardar: 1 };
	}
	return { activar_al_guardar: 0, omitir_pago_al_guardar: 0 };
};

club_management_socio_alta_guiada._build_datos = function (values) {
	const datos = {
		nombre: values.nombre,
		apellido: values.apellido,
		dni: values.dni,
		nacionalidad: values.nacionalidad,
		fecha_nacimiento: values.fecha_nacimiento,
		genero: values.genero,
		email: values.email,
		telefono_fijo: values.telefono_fijo,
		telefono_movil: values.telefono_movil,
		calle: values.calle,
		numero: values.numero,
		piso: values.piso,
		departamento: values.departamento,
		provincia: values.provincia,
		ciudad: values.ciudad,
		localidad_barrio: values.localidad_barrio,
		codigo_postal: values.codigo_postal,
		categoria: values.categoria,
	};
	if (values.categoria === "Menor") {
		datos.tipo_tutor = values.tipo_tutor;
		datos.tutor =
			values.tipo_tutor === "Socio" ? values.tutor_socio : values.tutor_no_socio;
	}
	return datos;
};

club_management_socio_alta_guiada._build_selecciones = function (values) {
	if (!values.inscribir_actividad || !values.actividad) {
		return null;
	}
	return JSON.stringify([
		{
			actividad: values.actividad,
			grupo: values.grupo || null,
			equipo: values.equipo || null,
		},
	]);
};

club_management_socio_alta_guiada._crear_socio = function (d, values, frm) {
	const flujo = club_management_socio_alta_guiada._map_flujo(values.flujo_destino);
	const datos = club_management_socio_alta_guiada._build_datos(values);
	const selecciones = club_management_socio_alta_guiada._build_selecciones(values);

	frappe.call({
		method: "club_management.members.api.socio_operaciones_desk.crear_socio_desk",
		args: {
			datos: JSON.stringify(datos),
			activar_al_guardar: flujo.activar_al_guardar,
			omitir_pago_al_guardar: flujo.omitir_pago_al_guardar,
			selecciones,
		},
		freeze: true,
		callback(r) {
			if (!r.exc && r.message) {
				d.hide();
				if (frm && frm.is_new()) {
					frappe.set_route("Form", "Socio", r.message.socio);
				} else {
					frappe.set_route("Form", "Socio", r.message.socio);
				}
				frappe.show_alert({
					message: __("Socio creado — {0}", [r.message.estado]),
					indicator: "green",
				});
			}
		},
	});
};
