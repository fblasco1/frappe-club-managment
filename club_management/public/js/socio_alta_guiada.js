/* global frappe */
frappe.provide("club_management_socio_alta_guiada");

club_management_socio_alta_guiada.open = function (frm) {
	const prefill = frm ? club_management_socio_alta_guiada._collect_from_frm(frm) : {};
	const d = new frappe.ui.Dialog({
		title: __("Alta de Socio"),
		size: "extra-large",
		fields: [
			{ fieldtype: "Section Break", label: __("Datos personales") },
			{
				fieldname: "numero_socio",
				fieldtype: "Int",
				label: __("Número de socio"),
				description: __(
					"Opcional. Si se deja vacío se asigna el siguiente disponible. Debe ser único."
				),
				default: prefill.numero_socio,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "nombre",
				fieldtype: "Data",
				label: __("Nombre"),
				reqd: 1,
				default: prefill.nombre,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "apellido",
				fieldtype: "Data",
				label: __("Apellido"),
				reqd: 1,
				default: prefill.apellido,
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "dni",
				fieldtype: "Data",
				label: __("DNI"),
				reqd: 1,
				default: prefill.dni,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "nacionalidad",
				fieldtype: "Link",
				label: __("Nacionalidad"),
				options: "Country",
				reqd: 1,
				default: prefill.nacionalidad || "Argentina",
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "fecha_nacimiento",
				fieldtype: "Date",
				label: __("Fecha de nacimiento"),
				reqd: 1,
				default: prefill.fecha_nacimiento,
				onchange: () => club_management_socio_alta_guiada._sugerir_categoria(d),
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "genero",
				fieldtype: "Select",
				label: __("Género"),
				options: "\nMasculino\nFemenino\nOtro\nPrefiero no decir",
				reqd: 1,
				default: prefill.genero,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "email",
				fieldtype: "Data",
				label: __("Email"),
				options: "Email",
				reqd: 1,
				default: prefill.email,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "telefono_fijo",
				fieldtype: "Data",
				label: __("Teléfono fijo"),
				default: prefill.telefono_fijo,
			},
			{ fieldtype: "Column Break" },
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
			{ fieldtype: "Column Break" },
			{
				fieldname: "numero",
				fieldtype: "Data",
				label: __("Número"),
				default: prefill.numero,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "piso",
				fieldtype: "Data",
				label: __("Piso"),
				default: prefill.piso,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "departamento",
				fieldtype: "Data",
				label: __("Departamento"),
				default: prefill.departamento,
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "provincia",
				fieldtype: "Data",
				label: __("Provincia"),
				default: prefill.provincia,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "ciudad",
				fieldtype: "Data",
				label: __("Ciudad"),
				default: prefill.ciudad,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "localidad_barrio",
				fieldtype: "Data",
				label: __("Localidad / Barrio"),
				default: prefill.localidad_barrio,
			},
			{ fieldtype: "Column Break" },
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
				onchange: () => club_management_socio_alta_guiada._wire_tutor_fields(d),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "tipo_tutor",
				fieldtype: "Select",
				label: __("Tipo de tutor (opcional)"),
				options: "\nSocio\nTutor No Socio",
				depends_on: "eval:doc.categoria=='Menor'",
				description: __(
					"Opcional en el alta. Puede completarlo después. Si crea un tutor no socio, use el botón del asistente (no abandona este formulario)."
				),
				default: prefill.tipo_tutor,
				onchange: () => club_management_socio_alta_guiada._wire_tutor_fields(d),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "tutor_socio",
				fieldtype: "Link",
				label: __("Tutor (socio)"),
				options: "Socio",
				only_select: 1,
				depends_on: "eval:doc.categoria=='Menor' && doc.tipo_tutor=='Socio'",
				default: prefill.tipo_tutor === "Socio" ? prefill.tutor : "",
			},
			{
				fieldname: "tutor_no_socio",
				fieldtype: "Link",
				label: __("Tutor (no socio)"),
				options: "Tutor No Socio",
				only_select: 1,
				depends_on: "eval:doc.categoria=='Menor' && doc.tipo_tutor=='Tutor No Socio'",
				default: prefill.tipo_tutor === "Tutor No Socio" ? prefill.tutor : "",
			},
			{ fieldtype: "Section Break", label: __("Inscripción (opcional)") },
			{
				fieldname: "inscribir_actividad",
				fieldtype: "Check",
				label: __("Inscribir en actividad al guardar"),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "actividad",
				fieldtype: "Link",
				label: __("Actividad"),
				options: "Actividad",
				depends_on: "eval:doc.inscribir_actividad",
				get_query: () => ({ filters: { habilitada: 1 } }),
				onchange: () => club_management.inscripcion_cascada.load_grupos_dialog(d),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "grupo",
				fieldtype: "Link",
				label: __("Grupo / tira"),
				options: "Grupo Actividad",
				depends_on: "eval:doc.inscribir_actividad",
				onchange: () => club_management.inscripcion_cascada.load_equipos_dialog(d),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "equipo",
				fieldtype: "Link",
				label: __("Equipo / categoría"),
				options: "Equipo Actividad",
				depends_on: "eval:doc.inscribir_actividad",
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "crear_socio_btn",
				fieldtype: "Button",
				label: __("Crear socio"),
				click() {
					const values = d.get_values();
					if (!values) {
						return;
					}
					club_management_socio_alta_guiada._crear_socio(d, values, frm);
				},
			},
		],
	});
	d.show();
	d.$wrapper.addClass("club-alta-socio-dialog");
	d.$wrapper.find(".modal-footer").hide();
	club_management.inscripcion_cascada.setup_dialog_cascada(d);
	club_management_socio_alta_guiada._wire_tutor_fields(d);
	if (prefill.fecha_nacimiento) {
		club_management_socio_alta_guiada._sugerir_categoria(d);
	}
};

/** Evita navegar al Form al crear tutor; ofrece alta anidada que vuelve al asistente. */
club_management_socio_alta_guiada._wire_tutor_fields = function (d) {
	for (const fieldname of ["tutor_socio", "tutor_no_socio"]) {
		const field = d.get_field(fieldname);
		if (field?.df) {
			field.df.only_select = 1;
		}
	}
	const field = d.get_field("tutor_no_socio");
	if (!field?.$wrapper) {
		return;
	}
	field.$wrapper.find(".club-crear-tns").remove();
	if (d.get_value("tipo_tutor") !== "Tutor No Socio") {
		return;
	}
	const $btn = $(
		`<button type="button" class="btn btn-xs btn-default club-crear-tns" style="margin-top: 6px;">
			${__("Crear tutor no socio")}
		</button>`
	);
	$btn.on("click", (e) => {
		e.preventDefault();
		club_management_socio_alta_guiada._abrir_dialog_tutor_no_socio(d);
	});
	field.$wrapper.append($btn);
};

club_management_socio_alta_guiada._abrir_dialog_tutor_no_socio = function (parent_dialog) {
	const nested = new frappe.ui.Dialog({
		title: __("Nuevo tutor no socio"),
		size: "large",
		fields: [
			{ fieldtype: "Section Break", label: __("Datos personales") },
			{ fieldname: "nombre", fieldtype: "Data", label: __("Nombre"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "apellido", fieldtype: "Data", label: __("Apellido"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "dni", fieldtype: "Data", label: __("DNI"), reqd: 1 },
			{ fieldtype: "Section Break" },
			{
				fieldname: "nacionalidad",
				fieldtype: "Link",
				label: __("Nacionalidad"),
				options: "Country",
				reqd: 1,
				default: "Argentina",
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "fecha_nacimiento",
				fieldtype: "Date",
				label: __("Fecha de nacimiento"),
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "genero",
				fieldtype: "Select",
				label: __("Género"),
				options: "\nMasculino\nFemenino\nOtro\nPrefiero no decir",
				reqd: 1,
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "email",
				fieldtype: "Data",
				label: __("Email"),
				options: "Email",
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{ fieldname: "telefono_fijo", fieldtype: "Data", label: __("Teléfono fijo") },
			{ fieldtype: "Column Break" },
			{
				fieldname: "telefono_movil",
				fieldtype: "Data",
				label: __("Teléfono móvil"),
				reqd: 1,
			},
			{ fieldtype: "Section Break", label: __("Domicilio") },
			{ fieldname: "calle", fieldtype: "Data", label: __("Calle"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "numero", fieldtype: "Data", label: __("Número") },
			{ fieldtype: "Column Break" },
			{ fieldname: "piso", fieldtype: "Data", label: __("Piso") },
			{ fieldtype: "Column Break" },
			{ fieldname: "departamento", fieldtype: "Data", label: __("Departamento") },
			{ fieldtype: "Section Break" },
			{ fieldname: "provincia", fieldtype: "Data", label: __("Provincia"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "ciudad", fieldtype: "Data", label: __("Ciudad") },
			{ fieldtype: "Column Break" },
			{
				fieldname: "localidad_barrio",
				fieldtype: "Data",
				label: __("Localidad / Barrio"),
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{ fieldname: "codigo_postal", fieldtype: "Data", label: __("Código postal"), reqd: 1 },
		],
		primary_action_label: __("Guardar y volver al alta"),
		primary_action(values) {
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "Tutor No Socio",
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
					},
				},
				freeze: true,
				freeze_message: __("Creando tutor…"),
				callback(r) {
					if (r.exc || !r.message?.name) {
						return;
					}
					nested.hide();
					parent_dialog.set_value("tipo_tutor", "Tutor No Socio").then(() => {
						parent_dialog.set_value("tutor_no_socio", r.message.name);
						club_management_socio_alta_guiada._wire_tutor_fields(parent_dialog);
					});
					frappe.show_alert({
						message: __("Tutor creado: {0}", [r.message.name]),
						indicator: "green",
					});
				},
			});
		},
		secondary_action_label: __("Volver al alta de socio"),
		secondary_action() {
			nested.hide();
		},
	});
	nested.show();
};

club_management_socio_alta_guiada._collect_from_frm = function (frm) {
	const campos = [
		"numero_socio",
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
				d.set_value("categoria", r.message.categoria).then(() => {
					club_management_socio_alta_guiada._wire_tutor_fields(d);
				});
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
	if (values.numero_socio) {
		datos.numero_socio = values.numero_socio;
	}
	if (values.categoria === "Menor") {
		const tutor =
			values.tipo_tutor === "Socio"
				? values.tutor_socio
				: values.tipo_tutor === "Tutor No Socio"
					? values.tutor_no_socio
					: null;
		if (values.tipo_tutor && tutor) {
			datos.tipo_tutor = values.tipo_tutor;
			datos.tutor = tutor;
		}
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
	const datos = club_management_socio_alta_guiada._build_datos(values);
	const selecciones = club_management_socio_alta_guiada._build_selecciones(values);

	frappe.call({
		method: "club_management.members.api.socio_operaciones_desk.crear_socio_desk",
		args: {
			datos: JSON.stringify(datos),
			activar_al_guardar: 1,
			omitir_pago_al_guardar: 0,
			selecciones,
		},
		freeze: true,
		callback(r) {
			if (!r.exc && r.message) {
				d.hide();
				frappe.set_route("Form", "Socio", r.message.socio);
				frappe.show_alert({
					message: __("Socio creado — {0}", [r.message.estado]),
					indicator: "green",
				});
			}
		},
	});
};
