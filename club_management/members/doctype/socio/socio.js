frappe.ui.form.on("Socio", {
	refresh(frm) {
		const es_secretaria =
			frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager");
		if (!es_secretaria) {
			return;
		}
		if (!frm.is_new() && frm.doc.nombre_completo) {
			frm.page.set_title(frm.doc.nombre_completo);
		}
		frm.set_df_property("grupo_familiar", "hidden", 1);
		frm.set_df_property("solicitud_origen", "hidden", 1);
		if (frm.is_new()) {
			frm.set_df_property("numero_socio", "read_only", 0);
			frm.set_df_property(
				"numero_socio",
				"description",
				__(
					"Opcional. Si se deja vacío se asigna el siguiente número disponible. Debe ser único."
				)
			);
		} else {
			frm.set_df_property("numero_socio", "read_only", 1);
		}
		if (frm.is_new()) {
			club_management_socio_desk.relax_adjuntos_alta_manual(frm);
			club_management_socio_desk.relax_tutor_alta_manual(frm);
			club_management_socio_desk.add_alta_guiada_button(frm);
			if (!frm._alta_guiada_opened) {
				frm._alta_guiada_opened = true;
				club_management_socio_alta_guiada.open(frm);
			}
			return;
		}
		club_management_socio_desk.relax_validacion_edicion_secretaria(frm);
		club_management_socio_desk.add_operaciones_buttons(frm);
		club_management_socio_desk.render_datos_criticos_alert(frm);
		club_management_socio_desk.render_inscripciones(frm);
		club_management_socio_desk.render_becas(frm);
		club_management_socio_desk.render_deuda_pendiente(frm);
		club_management_socio_desk.render_historial_pagos(frm);
	},
	categoria(frm) {
		if (!(frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager"))) {
			return;
		}
		if (frm.is_new()) {
			club_management_socio_desk.relax_tutor_alta_manual(frm);
			return;
		}
		club_management_socio_desk.relax_validacion_edicion_secretaria(frm);
	},
});

frappe.provide("club_management_socio_desk");

/** Edición Desk de un Socio existente por Secretaría / System Manager. */
club_management_socio_desk.es_edicion_secretaria_socio = function (frm) {
	if (!frm || frm.doctype !== "Socio" || frm.is_new()) {
		return false;
	}
	return (
		frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager")
	);
};

/**
 * Frappe v16 valida mandatory en cliente (`check_mandatory`, incluye
 * `mandatory_depends_on`). Parche global al cargar el script: no depende de
 * override de `frm.save` ni de flags asíncronos.
 */
(function patch_socio_mandatory_secretaria() {
	if (frappe.ui.form._club_socio_mandatory_patched) {
		return;
	}
	frappe.ui.form._club_socio_mandatory_patched = true;

	const original_check_mandatory = frappe.ui.form.check_mandatory;
	frappe.ui.form.check_mandatory = function (frm) {
		if (club_management_socio_desk.es_edicion_secretaria_socio(frm)) {
			return true;
		}
		return original_check_mandatory(frm);
	};

	const original_ui_save = frappe.ui.form.save;
	frappe.ui.form.save = function (frm, action, callback, btn) {
		if (club_management_socio_desk.es_edicion_secretaria_socio(frm)) {
			void club_management_socio_desk.advertir_datos_criticos_faltantes(frm, {
				al_guardar: true,
			});
		}
		return original_ui_save(frm, action, callback, btn);
	};
})();

club_management_socio_desk._CAMPOS_ALTA_MANUAL = [
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
	"foto_perfil",
	"dni_frente",
	"dni_dorso",
	"ficha_medica",
	"tipo_tutor",
	"tutor",
];

club_management_socio_desk.relax_adjuntos_alta_manual = function (frm) {
	const adjuntos = ["foto_perfil", "dni_frente", "dni_dorso", "ficha_medica"];
	for (const fieldname of adjuntos) {
		frm.set_df_property(fieldname, "reqd", 0);
		frm.set_df_property(fieldname, "hidden", 1);
	}
	frm.set_df_property("documentos_section", "hidden", 1);
};

/** Tutor opcional en alta Desk (queda como dato crítico si falta en Menor). */
club_management_socio_desk.relax_tutor_alta_manual = function (frm) {
	for (const fieldname of ["tipo_tutor", "tutor"]) {
		frm.set_df_property(fieldname, "reqd", 0);
		frm.set_df_property(fieldname, "mandatory_depends_on", "");
	}
};

club_management_socio_desk.relax_adjuntos_edicion_secretaria = function (frm) {
	const adjuntos = ["foto_perfil", "dni_frente", "dni_dorso", "ficha_medica"];
	for (const fieldname of adjuntos) {
		frm.set_df_property(fieldname, "reqd", 0);
		frm.set_df_property(fieldname, "hidden", 0);
	}
	frm.set_df_property("documentos_section", "hidden", 0);
};

/** Quita obligatoriedad Desk de campos críticos pero no bloqueantes en edición. */
club_management_socio_desk.relax_validacion_edicion_secretaria = function (frm) {
	club_management_socio_desk.relax_adjuntos_edicion_secretaria(frm);
	const opcionales_en_edicion = [
		"email",
		"telefono_movil",
		"calle",
		"ciudad",
		"provincia",
		"localidad_barrio",
		"codigo_postal",
		"tipo_tutor",
		"tutor",
	];
	for (const fieldname of opcionales_en_edicion) {
		frm.set_df_property(fieldname, "reqd", 0);
	}
};

club_management_socio_desk.fetch_datos_criticos_faltantes = function (frm) {
	return frappe
		.xcall("club_management.members.api.socio_operaciones_desk.list_datos_criticos_faltantes_desk", {
			doc: frm.doc,
		})
		.then((rows) => rows || []);
};

club_management_socio_desk.advertir_datos_criticos_faltantes = async function (frm, opts = {}) {
	const faltantes = await club_management_socio_desk.fetch_datos_criticos_faltantes(frm);
	if (!faltantes.length) {
		return [];
	}
	const labels = faltantes.map((row) => row.label).join(", ");
	const mensaje = opts.al_guardar
		? __("Se guardará el socio, pero aún faltan datos críticos: {0}", [labels])
		: __("Faltan datos críticos: {0}", [labels]);
	if (opts.al_guardar) {
		frappe.show_alert({ message: mensaje, indicator: "orange" }, 7);
	} else {
		frappe.msgprint({
			title: __("Datos críticos incompletos"),
			message: mensaje,
			indicator: "orange",
		});
	}
	return faltantes;
};

club_management_socio_desk.render_datos_criticos_alert = function (frm) {
	const $host = frm.layout.wrapper.find(".club-datos-criticos-alert");
	$host.remove();
	club_management_socio_desk.fetch_datos_criticos_faltantes(frm).then((faltantes) => {
		if (!faltantes.length) {
			return;
		}
		const labels = faltantes.map((row) => row.label).join(", ");
		const $alert = $(`
			<div class="club-datos-criticos-alert alert alert-warning" role="status" style="margin: 0.75rem 0;">
				<strong>${__("Datos críticos incompletos")}</strong>
				<div class="small">${frappe.utils.escape_html(labels)}</div>
			</div>
		`);
		frm.layout.wrapper.prepend($alert);
	});
};

club_management_socio_desk.add_alta_guiada_button = function (frm) {
	frm.page.set_primary_action(__("Alta guiada"), () =>
		club_management_socio_alta_guiada.open(frm)
	);
};

club_management_socio_desk.add_operaciones_buttons = function (frm) {
	const estado = frm.doc.estado;
	const group = __("Operación Secretaría");

	if (estado === "Pendiente de Pago") {
		frm.add_custom_button(
			__("Omitir pago (alta manual)"),
			() => club_management_socio_desk.call_op(frm, "omitir_pago"),
			group
		);
	}
	if (["Pendiente de Pago", "Pendiente de Inscripción", "Suspendido", "Pendiente de Validación"].includes(estado)) {
		frm.add_custom_button(__("Activar socio"), () => club_management_socio_desk.call_op(frm, "activar_socio"), group);
	}
	if (estado === "Pendiente de Inscripción" || estado === "Activo") {
		frm.add_custom_button(
			__("Inscribir en actividades"),
			() => club_management_socio_desk.dialog_inscripcion(frm),
			group
		);
	}
	if (estado === "Activo") {
		frm.add_custom_button(
			__("Marcar moroso"),
			() => club_management_socio_desk.call_op(frm, "marcar_socio_moroso"),
			group
		);
		frm.add_custom_button(
			__("Suspender"),
			() => club_management_socio_desk.prompt_motivo(frm, "suspender_socio_desk"),
			group
		);
	}
	if (estado === "Moroso") {
		frm.add_custom_button(
			__("Reactivar"),
			() => club_management_socio_desk.call_op(frm, "reactivar_socio_desk"),
			group
		);
	}
	if (estado === "Baja") {
		frm.add_custom_button(
			__("Dar de alta"),
			() => club_management_socio_desk.prompt_motivo(frm, "dar_alta"),
			group
		);
	}
	if (["Activo", "Moroso", "Suspendido", "Pendiente de Pago", "Pendiente de Inscripción"].includes(estado)) {
		frm.add_custom_button(
			__("Dar de baja"),
			() => club_management_socio_desk.prompt_motivo(frm, "dar_baja", { require_motivo: true }),
			group
		);
	}
	if (estado !== "Baja") {
		frm.add_custom_button(__("Crear beca"), () => club_management_socio_desk.crear_beca(frm), group);
		frm.add_custom_button(
			__("Nueva bonificación arancel"),
			() => club_management_socio_desk.crear_bonificacion_arancel(frm),
			group
		);
		frm.add_custom_button(
			__("Corregir número de socio"),
			() => club_management_socio_desk.dialog_corregir_numero(frm),
			group
		);
	}

	const cobranza = __("Cobranza manual");
	frm.add_custom_button(
		__("Nuevo cargo extra"),
		() => club_management_socio_desk.nuevo_cargo_extra(frm),
		cobranza
	);
	frm.add_custom_button(__("Generar cargo"), () => club_management_socio_desk.generar_cargo(frm), cobranza);
	frm.add_custom_button(
		__("Cancelar factura impaga"),
		() => club_management_socio_desk.dialog_cancelar_factura_impaga(frm),
		cobranza
	);
	if (flt(frm.doc.saldo_deuda) > 0) {
		frm.add_custom_button(
			__("Registrar cobro"),
			() => club_management_socio_desk.dialog_registrar_cobro(frm),
			cobranza
		);
	}
	frm.add_custom_button(
		__("Actualizar saldo deuda"),
		() => club_management_socio_desk.actualizar_saldo(frm),
		cobranza
	);
};

club_management_socio_desk.dialog_corregir_numero = function (frm) {
	frappe.prompt(
		[
			{
				fieldname: "nuevo_numero",
				fieldtype: "Int",
				label: __("Nuevo número de socio"),
				reqd: 1,
				description: __(
					"Usar cuando el número actual es provisional. Actualiza el identificador y todos los vínculos."
				),
			},
		],
		(values) => {
			frappe.confirm(
				__(
					"¿Cambiar el número de socio de {0} a {1}? Esta acción renombra el documento.",
					[frm.doc.name, values.nuevo_numero]
				),
				() => {
					frappe.call({
						method: "club_management.members.api.socio_operaciones_desk.corregir_numero_socio",
						args: { socio: frm.doc.name, nuevo_numero: values.nuevo_numero },
						freeze: true,
						callback(r) {
							if (!r.exc && r.message && r.message.socio) {
								frappe.show_alert({
									message: __("Número actualizado: {0}", [r.message.socio]),
									indicator: "green",
								});
								frappe.set_route("Form", "Socio", r.message.socio);
							}
						},
					});
				}
			);
		},
		__("Corregir número de socio"),
		__("Confirmar")
	);
};

club_management_socio_desk.call_op = function (frm, method, extra_args = {}) {
	frappe.call({
		method: `club_management.members.api.socio_operaciones_desk.${method}`,
		args: { socio: frm.doc.name, ...extra_args },
		freeze: true,
		callback(r) {
			if (!r.exc) {
				frappe.show_alert({ message: __("Estado actualizado"), indicator: "green" });
				frm.reload_doc();
			}
		},
	});
};

club_management_socio_desk.prompt_motivo = function (frm, method, opts = {}) {
	frappe.prompt(
		[{ fieldname: "motivo", fieldtype: "Small Text", label: __("Motivo"), reqd: !!opts.require_motivo }],
		(values) => club_management_socio_desk.call_op(frm, method, { motivo: values.motivo }),
		__("Confirmar"),
		__("Continuar")
	);
};

club_management_socio_desk.dialog_inscripcion = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Inscribir en actividades"),
		fields: [
			{
				fieldname: "actividad",
				fieldtype: "Link",
				label: __("Actividad"),
				options: "Actividad",
				get_query: () => ({ filters: { habilitada: 1 } }),
				reqd: 1,
				onchange: () => club_management.inscripcion_cascada.load_grupos_dialog(d),
			},
			{
				fieldname: "grupo",
				fieldtype: "Link",
				label: __("Grupo / tira"),
				options: "Grupo Actividad",
				onchange: () => club_management.inscripcion_cascada.load_equipos_dialog(d),
			},
			{
				fieldname: "equipo",
				fieldtype: "Link",
				label: __("Equipo / categoría"),
				options: "Equipo Actividad",
			},
			{
				fieldname: "selecciones_json",
				fieldtype: "Small Text",
				label: __("Actividades en cola"),
				read_only: 1,
				hidden: 1,
			},
		],
		primary_action_label: __("Confirmar inscripción"),
		primary_action() {
			club_management.inscripcion_cascada
				.collect_selecciones_dialog(d)
				.then((selecciones) => {
					frappe.call({
						method: "club_management.members.api.socio_operaciones_desk.inscribir_actividades",
						args: { socio: frm.doc.name, selecciones: JSON.stringify(selecciones) },
						freeze: true,
						callback(r) {
							if (!r.exc) {
								d.hide();
								frm.reload_doc();
								frappe.show_alert({
									message: __("Inscripción registrada"),
									indicator: "green",
								});
							}
						},
					});
				})
				.catch(() => {});
		},
		secondary_action_label: __("Agregar otra actividad"),
		secondary_action() {
			club_management.inscripcion_cascada.push_selection_dialog(d).catch(() => {});
		},
	});
	d.show();
	club_management.inscripcion_cascada.setup_dialog_cascada(d);
};

club_management_socio_desk.load_equipos = function (d) {
	club_management.inscripcion_cascada.load_equipos_dialog(d);
};

club_management_socio_desk.load_grupos = function (d) {
	club_management.inscripcion_cascada.load_grupos_dialog(d);
};

club_management_socio_desk.nuevo_cargo_extra = function (frm) {
	frappe.call({
		method: "club_management.members.api.cargo_extra_desk.list_conceptos_cargo_extra",
		args: { socio: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.exc) return;
			const conceptos = r.message || [];
			if (!conceptos.length) {
				frappe.msgprint(
					__("No hay conceptos de cargo extra para este socio (actividades + generales).")
				);
				return;
			}
			club_management_socio_desk.dialog_nuevo_cargo_extra(frm, conceptos);
		},
	});
};

club_management_socio_desk.dialog_nuevo_cargo_extra = function (frm, conceptos) {
	const codes = conceptos.map((c) => c.item_code);
	const by_code = {};
	conceptos.forEach((c) => {
		by_code[c.item_code] = c;
	});
	const d = new frappe.ui.Dialog({
		title: __("Nuevo cargo extra"),
		fields: [
			{
				fieldname: "tipo_cargo",
				fieldtype: "Select",
				label: __("Tipo de cargo"),
				options: "Cuota Federativa\nMulta\nViaje\nOtro",
				default: "Multa",
				reqd: 1,
				onchange() {
					const tipo = d.get_value("tipo_cargo");
					if (tipo === "Cuota Federativa") {
						d.set_value("modo_cobro", "Recurrente");
					} else {
						d.set_value("modo_cobro", "Unico");
					}
					if (!d.get_value("titulo")) {
						d.set_value("titulo", tipo);
					}
				},
			},
			{
				fieldname: "titulo",
				fieldtype: "Data",
				label: __("Título"),
				reqd: 1,
			},
			{
				fieldname: "modo_cobro",
				fieldtype: "Select",
				label: __("Modo de cobro"),
				options: "Unico\nRecurrente",
				default: "Unico",
				reqd: 1,
			},
			{
				fieldname: "item",
				fieldtype: "Link",
				label: __("Concepto"),
				options: "Item",
				reqd: 1,
				get_query: () => ({ filters: { name: ["in", codes] } }),
				onchange() {
					const code = d.get_value("item");
					const concepto = by_code[code];
					if (!concepto) return;
					if (!d.get_value("titulo")) {
						d.set_value("titulo", concepto.item_name || code);
					}
					const rate = flt(concepto.standard_rate);
					if (rate > 0 && !flt(d.get_value("monto"))) {
						d.set_value("monto", rate);
					}
				},
			},
			{
				fieldname: "monto",
				fieldtype: "Currency",
				label: __("Monto"),
				reqd: 1,
			},
			{
				fieldname: "fecha_desde",
				fieldtype: "Date",
				label: __("Vigente desde"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "fecha_hasta",
				fieldtype: "Date",
				label: __("Vigente hasta"),
				depends_on: "eval:doc.modo_cobro==='Recurrente'",
				mandatory_depends_on: "eval:doc.modo_cobro==='Recurrente'",
			},
			{
				fieldname: "facturar_mes_corriente",
				fieldtype: "Check",
				label: __("Facturar este mes ahora (para poder cobrarlo)"),
				default: 1,
				depends_on: "eval:doc.modo_cobro==='Recurrente'",
			},
			{
				fieldname: "observaciones",
				fieldtype: "Small Text",
				label: __("Observaciones"),
			},
		],
		primary_action_label: __("Crear y facturar"),
		primary_action(values) {
			if (values.modo_cobro === "Recurrente" && !values.fecha_hasta) {
				frappe.msgprint(__("Indicá la fecha hasta para cargos recurrentes."));
				return;
			}
			d.hide();
			frappe.call({
				method: "club_management.members.api.cargo_extra_desk.crear_cargo_extra",
				args: {
					socio: frm.doc.name,
					titulo: values.titulo,
					tipo_cargo: values.tipo_cargo,
					modo_cobro: values.modo_cobro,
					item: values.item,
					monto: values.monto,
					fecha_desde: values.fecha_desde,
					fecha_hasta: values.fecha_hasta,
					observaciones: values.observaciones,
					facturar_mes_corriente: values.facturar_mes_corriente ? 1 : 0,
				},
				freeze: true,
				callback(res) {
					if (res.exc || !res.message) return;
					const msg = res.message;
					frm.reload_doc();
					const invoices = msg.sales_invoices || (msg.sales_invoice ? [msg.sales_invoice] : []);
					if (invoices.length) {
						frappe.confirm(
							__("Cargo facturado ({0}). ¿Registrar cobro ahora?", [invoices.join(", ")]),
							() => {
								frappe.call({
									method: "club_management.members.api.cobranza_desk.list_facturas_pendientes",
									args: { socio: frm.doc.name },
									callback(pend) {
										if (pend.exc) return;
										const wanted = new Set(invoices);
										const rows = (pend.message || []).filter((row) =>
											wanted.has(row.name)
										);
										if (!rows.length) {
											frappe.msgprint(__("No hay saldo pendiente para cobrar."));
											return;
										}
										club_management_socio_desk.prompt_cobro_multi_factura(frm, rows);
									},
								});
							}
						);
					} else {
						frappe.msgprint(
							__(
								"Cargo recurrente creado. Usá «Generar cargo» o abrí el cargo y «Facturar mes corriente» para cobrarlo."
							)
						);
					}
				},
			});
		},
	});
	d.show();
};

club_management_socio_desk.crear_beca = function (frm) {
	frappe.route_options = { socio: frm.doc.name };
	frappe.new_doc("Beca Socio");
};

club_management_socio_desk.crear_bonificacion_arancel = function (frm) {
	frappe.route_options = { socio: frm.doc.name };
	frappe.new_doc("Bonificacion Arancel");
};

club_management_socio_desk._vigencia_indicator = function (label) {
	const map = {
		Vigente: "green",
		Pendiente: "blue",
		Vencida: "grey",
		Cancelada: "red",
	};
	return map[label] || "orange";
};

club_management_socio_desk.render_becas = function (frm) {
	if (!frm.fields_dict.actividad || frm.is_new()) {
		return;
	}

	const $section = frm.fields_dict.actividad.$wrapper.closest(".form-section");
	let $panel = $section.find(".club-becas-panel");
	if (!$panel.length) {
		$panel = $('<div class="club-becas-panel" style="margin-top: 1rem;"></div>');
		const $inscripciones = $section.find(".club-inscripciones-panel");
		if ($inscripciones.length) {
			$inscripciones.after($panel);
		} else {
			frm.fields_dict.actividad.$wrapper.after($panel);
		}
	}

	$panel.html(`<p class="text-muted small">${__("Cargando becas…")}</p>`);

	frappe.call({
		method: "club_management.members.api.socio_operaciones_desk.list_becas_socio",
		args: { socio: frm.doc.name },
		callback(r) {
			if (r.exc) {
				$panel.empty();
				return;
			}
			const rows = r.message || [];
			if (!rows.length) {
				$panel.html(
					`<div class="text-muted small">${__("Sin becas asignadas.")}</div>`
				);
				return;
			}

			const $title = $(`<h6 class="mb-2">${__("Becas asignadas")}</h6>`);
			const $table = $(`
				<table class="table table-bordered table-sm club-becas-table">
					<thead>
						<tr>
							<th>${__("Tipo")}</th>
							<th>${__("Cuota %")}</th>
							<th>${__("Arancel %")}</th>
							<th>${__("Desde")}</th>
							<th>${__("Hasta")}</th>
							<th>${__("Estado")}</th>
							<th>${__("Vigencia")}</th>
							<th></th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			`);
			const $tbody = $table.find("tbody");

			rows.forEach((row) => {
				const vigencia = frappe.utils.escape_html(row.vigencia_label || "");
				const indicator = club_management_socio_desk._vigencia_indicator(row.vigencia_label);
				const cuota =
					row.tipo_beca === "Total" || row.tipo_beca === "Parcial Exime Cuota"
						? "100"
						: String(row.pct_cuota_social ?? 0);
				const arancel =
					row.tipo_beca === "Total" || row.tipo_beca === "Parcial Exime Arancel"
						? "100"
						: String(row.pct_arancel ?? 0);
				const $tr = $(`
					<tr data-beca="${frappe.utils.escape_html(row.name)}">
						<td>${frappe.utils.escape_html(row.tipo_beca || "")}</td>
						<td>${frappe.utils.escape_html(cuota)}</td>
						<td>${frappe.utils.escape_html(arancel)}</td>
						<td>${frappe.datetime.str_to_user(row.fecha_desde) || ""}</td>
						<td>${frappe.datetime.str_to_user(row.fecha_hasta) || ""}</td>
						<td>${frappe.utils.escape_html(row.estado || "")}</td>
						<td><span class="indicator-pill ${indicator} filterable">${vigencia}</span></td>
						<td class="text-right"></td>
					</tr>
				`);
				const $btn = $(`<button type="button" class="btn btn-xs btn-default">${__("Ver")}</button>`);
				$btn.on("click", () => frappe.set_route("Form", "Beca Socio", row.name));
				$tr.find("td:last").append($btn);
				$tbody.append($tr);
			});

			$panel.empty().append($title, $table);
		},
	});
};

club_management_socio_desk.generar_cargo = function (frm) {
	const first_of_month = frappe.datetime.month_start(frappe.datetime.get_today());
	const d = new frappe.ui.Dialog({
		title: __("Generar cargo"),
		fields: [
			{
				fieldname: "reference_date",
				fieldtype: "Date",
				label: __("Período (día 1 del mes)"),
				default: first_of_month,
				reqd: 1,
				description: __(
					"Elegí el mes a facturar (deuda histórica o mes corriente). Usa precios vigentes al emitir."
				),
			},
		],
		primary_action_label: __("Generar"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "club_management.members.api.cobranza_desk.generar_cargo",
				args: {
					socio: frm.doc.name,
					incluir_actividades: 1,
					reference_date: values.reference_date,
				},
				freeze: true,
				callback(r) {
					if (!r.exc && r.message) {
						const invoices = r.message.sales_invoices || [r.message.sales_invoice];
						frappe.msgprint(
							__("Facturas {0} — saldo {1}", [
								(invoices || []).filter(Boolean).join(", "),
								frappe.format(r.message.saldo_deuda, { fieldtype: "Currency" }),
							])
						);
						frm.reload_doc();
					}
				},
			});
		},
	});
	d.show();
};

club_management_socio_desk.dialog_cancelar_factura_impaga = function (frm) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_facturas_impagas_cancelables",
		args: { socio: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.exc) return;
			const rows = r.message || [];
			if (!rows.length) {
				frappe.msgprint(__("No hay facturas totalmente impagas para cancelar."));
				return;
			}
			const labels = rows.map((row) => {
				const monto = frappe.format(row.grand_total, { fieldtype: "Currency" });
				return `${row.name} — ${monto}`;
			});
			const pick_and_confirm = (invoice_name) => {
				frappe.confirm(
					__(
						"¿Cancelar la factura {0}? Luego podrá Generar cargo de nuevo con los datos corregidos.",
						[invoice_name]
					),
					() => club_management_socio_desk.ejecutar_cancelar_factura_impaga(frm, invoice_name)
				);
			};
			if (rows.length === 1) {
				pick_and_confirm(rows[0].name);
				return;
			}
			frappe.prompt(
				[
					{
						fieldname: "sales_invoice",
						fieldtype: "Select",
						label: __("Factura impaga"),
						options: labels.join("\n"),
						reqd: 1,
					},
				],
				(values) => {
					const invoice = (values.sales_invoice || "").split(" — ")[0].trim();
					pick_and_confirm(invoice);
				},
				__("Cancelar factura impaga"),
				__("Continuar")
			);
		},
	});
};

club_management_socio_desk.ejecutar_cancelar_factura_impaga = function (frm, sales_invoice) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.cancelar_factura_venta",
		args: { socio: frm.doc.name, sales_invoice },
		freeze: true,
		callback(r) {
			if (!r.exc && r.message) {
				frappe.show_alert({
					message: __("Factura cancelada: {0}", [sales_invoice]),
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
	});
};

club_management_socio_desk.dialog_registrar_cobro = function (frm) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_facturas_pendientes",
		args: { socio: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.exc) return;
			const rows = r.message || [];
			if (!rows.length) {
				frappe.msgprint(__("No hay facturas pendientes para este socio."));
				return;
			}
			club_management_socio_desk.prompt_cobro_multi_factura(frm, rows);
		},
	});
};

club_management_socio_desk._fmt_money = function (valor) {
	const n = flt(valor);
	if (typeof format_currency === "function") {
		return format_currency(n);
	}
	return String(n);
};

club_management_socio_desk.prompt_cobro_multi_factura = function (frm, rows) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_modos_pago_cobranza",
		callback(r) {
			if (r.exc) return;
			const modos = r.message || [];
			const labelToValue = {};
			const mode_options = modos
				.map((row) => {
					labelToValue[row.label] = row.value;
					return row.label;
				})
				.join("\n");
			const rowsByName = {};
			rows.forEach((row) => {
				rowsByName[row.name] = row;
			});
			const total = rows.reduce((acc, row) => acc + flt(row.outstanding_amount), 0);
			const invoice_options = rows.map((row) => {
				const saldo = frappe.format(row.outstanding_amount, { fieldtype: "Currency" });
				const concepto = row.concepto || row.name;
				const periodo = row.periodo_cobro ? `${row.periodo_cobro} · ` : "";
				return {
					label: `${periodo}${concepto} — ${row.name} — ${saldo}`,
					value: row.name,
					checked: true,
				};
			});
			const d = new frappe.ui.Dialog({
				title: __("Registrar cobro"),
				fields: [
					{
						fieldname: "posting_date",
						fieldtype: "Date",
						label: __("Fecha de cobro"),
						default: frappe.datetime.get_today(),
						reqd: 1,
					},
					{
						fieldname: "sales_invoices",
						fieldtype: "MultiCheck",
						label: __("Facturas a cobrar"),
						options: invoice_options,
						sort_options: false,
						select_all: true,
						reqd: 1,
					},
					{
						fieldname: "mora_resumen",
						fieldtype: "HTML",
						options: `<p class="text-muted small">${__("Calculando total con mora…")}</p>`,
					},
					{
						fieldname: "mode_1",
						fieldtype: "Select",
						label: __("Medio de pago"),
						options: mode_options,
						default: modos[0]?.label,
						reqd: 1,
					},
					{
						fieldname: "amount_1",
						fieldtype: "Currency",
						label: __("Monto medio 1"),
						default: total,
						reqd: 1,
					},
					{
						fieldname: "mode_2",
						fieldtype: "Select",
						label: __("Segundo medio (opcional)"),
						options: "\n" + mode_options,
						description: __("Para pago mixto (efectivo + transferencia, etc.)"),
					},
					{
						fieldname: "amount_2",
						fieldtype: "Currency",
						label: __("Monto medio 2"),
						default: 0,
					},
				],
				primary_action_label: __("Confirmar"),
				primary_action(values) {
					const selected = values.sales_invoices || [];
					if (!selected.length) {
						frappe.msgprint(__("Seleccioná al menos una factura."));
						return;
					}
					frappe.call({
						method: "club_management.members.api.cobranza_desk.preview_mora_al_cobro",
						args: {
							socio: frm.doc.name,
							sales_invoices: selected,
							posting_date: values.posting_date,
						},
						freeze: true,
						callback(preview_res) {
							if (preview_res.exc || !preview_res.message) {
								return;
							}
							const total_sel = flt(preview_res.message.total_exigido);
							club_management_socio_desk._aplicar_preview_mora(d, preview_res.message, rowsByName);

							const m1 = labelToValue[values.mode_1] || "Cash";
							let a2 = flt(values.amount_2);
							let a1 = flt(values.amount_1);
							// Un solo medio: forzar monto = total con mora (evita desfasaje por preview viejo).
							if (a2 <= 0) {
								a1 = total_sel;
								d.set_value("amount_1", a1);
							}

							const medios = [];
							if (a1 > 0) {
								medios.push({ mode_of_payment: m1, amount: a1 });
							}
							if (a2 > 0) {
								const m2 = labelToValue[values.mode_2];
								if (!m2) {
									frappe.msgprint(__("Elegí el segundo medio de pago."));
									return;
								}
								medios.push({ mode_of_payment: m2, amount: a2 });
							}
							if (!medios.length) {
								frappe.msgprint(__("Indicá al menos un medio con monto."));
								return;
							}
							const sum_medios = medios.reduce((acc, row) => acc + flt(row.amount), 0);
							if (Math.abs(sum_medios - total_sel) > 0.005) {
								frappe.msgprint(
									__(
										"La suma de medios ({0}) debe coincidir con el total a cobrar con mora ({1}).",
										[format_currency(sum_medios), format_currency(total_sel)]
									)
								);
								d.set_value("amount_1", Math.max(0, total_sel - a2));
								return;
							}
							d.hide();
							club_management_socio_desk.ejecutar_registrar_cobro_compuesto(
								frm,
								selected,
								medios,
								values.posting_date
							);
						},
					});
				},
			});

			let refresh_timer = null;
			const refresh_mora = () => {
				if (refresh_timer) {
					clearTimeout(refresh_timer);
				}
				refresh_timer = setTimeout(() => {
					const selected = d.get_value("sales_invoices") || [];
					if (!selected.length) {
						if (d.fields_dict.mora_resumen) {
							d.fields_dict.mora_resumen.$wrapper.html(
								`<p class="text-muted small">${__("Seleccioná al menos una factura.")}</p>`
							);
						}
						d.set_value("amount_1", 0);
						d.set_value("amount_2", 0);
						return;
					}
					frappe.call({
						method: "club_management.members.api.cobranza_desk.preview_mora_al_cobro",
						args: {
							socio: frm.doc.name,
							sales_invoices: selected,
							posting_date: d.get_value("posting_date"),
						},
						callback(preview_res) {
							if (preview_res.exc || !preview_res.message) {
								return;
							}
							club_management_socio_desk._aplicar_preview_mora(
								d,
								preview_res.message,
								rowsByName
							);
						},
					});
				}, 150);
			};

			// MultiCheck usa df.on_change (no onchange).
			d.fields_dict.sales_invoices.df.on_change = refresh_mora;
			d.fields_dict.posting_date.df.onchange = refresh_mora;
			d.fields_dict.amount_2.df.onchange = () => {
				const preview_total = flt(d._last_total_exigido);
				if (preview_total <= 0) {
					return;
				}
				const a2 = flt(d.get_value("amount_2"));
				d.set_value("amount_1", Math.max(0, flt(preview_total - a2, 2)));
			};
			d.show();
			refresh_mora();
		},
	});
};

club_management_socio_desk._aplicar_preview_mora = function (dialog, preview, rowsByName) {
	club_management_socio_desk._pintar_resumen_mora(dialog, preview);
	club_management_socio_desk._actualizar_labels_facturas_mora(dialog, preview, rowsByName || {});
	const total = flt(preview.total_exigido);
	dialog._last_total_exigido = total;
	const a2 = flt(dialog.get_value("amount_2"));
	dialog.set_value("amount_1", Math.max(0, flt(total - a2, 2)));
	if (a2 > total) {
		dialog.set_value("amount_2", 0);
		dialog.set_value("amount_1", total);
	}
};

club_management_socio_desk._actualizar_labels_facturas_mora = function (dialog, preview, rowsByName) {
	const control = dialog.fields_dict.sales_invoices;
	if (!control || !control.options) {
		return;
	}
	const by_invoice = {};
	(preview.detalle || []).forEach((row) => {
		by_invoice[row.invoice] = row;
	});
	control.options.forEach((opt) => {
		const base = rowsByName[opt.value] || {};
		const info = by_invoice[opt.value];
		const concepto = (info && info.concepto) || base.concepto || opt.value;
		const periodo = (info && info.periodo) || base.periodo_cobro || "";
		const monto = info ? flt(info.monto_exigido) : flt(base.outstanding_amount);
		const monto_txt = club_management_socio_desk._fmt_money(monto);
		const mora_txt =
			info && info.aplica_mora
				? ` · ${__("con mora")} (+${club_management_socio_desk._fmt_money(info.monto_ajuste)})`
				: "";
		const bonif_txt =
			info && info.aplica_bonificacion
				? ` · ${__("bonif.")} (−${club_management_socio_desk._fmt_money(info.monto_bonificacion)})`
				: "";
		const periodo_txt = periodo ? `${periodo} · ` : "";
		opt.label = `${periodo_txt}${concepto} — ${opt.value} — ${monto_txt}${mora_txt}${bonif_txt}`;
		if (opt.$checkbox) {
			opt.$checkbox.find(".label-area").text(opt.label);
		}
	});
};

club_management_socio_desk._pintar_resumen_mora = function (dialog, preview) {
	const detalle = preview.detalle || [];
	const total = flt(preview.total_exigido);
	const ajustes = flt(preview.total_ajustes);
	const bonif = flt(preview.total_bonificacion);
	let html = `<div class="small" style="margin: 0.5rem 0;">`;
	html += `<p style="margin-bottom:0.4rem;"><b>${__("Total a cobrar")}:</b> ${frappe.utils.escape_html(
		club_management_socio_desk._fmt_money(total)
	)}`;
	if (ajustes > 0) {
		html += ` <span class="text-danger" style="white-space:nowrap;">(+${frappe.utils.escape_html(
			club_management_socio_desk._fmt_money(ajustes)
		)} ${__("mora")})</span>`;
	}
	if (bonif > 0) {
		html += ` <span class="text-success" style="white-space:nowrap;">(−${frappe.utils.escape_html(
			club_management_socio_desk._fmt_money(bonif)
		)} ${__("bonificación")})</span>`;
	}
	html += `</p><ul style="margin:0;padding-left:1.2rem;">`;
	detalle.forEach((row) => {
		const periodo = frappe.utils.escape_html(row.periodo || "—");
		const concepto = frappe.utils.escape_html(row.concepto || row.invoice || "");
		const exigido = frappe.utils.escape_html(club_management_socio_desk._fmt_money(row.monto_exigido));
		let extra = "";
		if (row.aplica_mora && row.composicion) {
			extra += `<br/><span class="text-muted">${frappe.utils.escape_html(row.composicion)}</span>`;
		}
		if (row.aplica_bonificacion && flt(row.monto_bonificacion) > 0) {
			const motivos = (row.bonificacion_motivos || []).join("; ") || "";
			extra += `<br/><span class="text-success">${__(
				"Bonificación arancel"
			)}: −${frappe.utils.escape_html(
				club_management_socio_desk._fmt_money(row.monto_bonificacion)
			)}${motivos ? ` — ${frappe.utils.escape_html(motivos)}` : ""}</span>`;
		}
		html += `<li><b>${periodo}</b> ${concepto}: ${exigido}${extra}</li>`;
	});
	html += `</ul></div>`;
	if (dialog.fields_dict.mora_resumen) {
		dialog.fields_dict.mora_resumen.$wrapper.html(html);
	}
};

club_management_socio_desk.ejecutar_registrar_cobro_compuesto = function (
	frm,
	sales_invoices,
	medios,
	posting_date
) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.registrar_cobro_compuesto",
		args: {
			socio: frm.doc.name,
			sales_invoices,
			medios,
			posting_date,
		},
		freeze: true,
		callback(res) {
			if (!res.exc && res.message) {
				const pes = res.message.payment_entries || [res.message.payment_entry];
				frappe.show_alert({
					message: __("Cobro registrado: {0}", [(pes || []).filter(Boolean).join(", ")]),
					indicator: "green",
				});
				const recibos = res.message.recibos || (res.message.recibo ? [res.message.recibo] : []);
				(recibos || []).forEach((recibo) => {
					if (recibo && club_management_recibo_pago?.imprimir_despues_cobro) {
						club_management_recibo_pago.imprimir_despues_cobro(recibo);
					}
				});
				frm.reload_doc();
			}
		},
	});
};

club_management_socio_desk.prompt_modo_y_registrar_cobro = function (frm, invoice_row) {
	club_management_socio_desk.prompt_cobro_multi_factura(frm, [invoice_row]);
};

club_management_socio_desk.ejecutar_registrar_cobro = function (
	frm,
	invoice_row,
	mode_of_payment,
	posting_date
) {
	club_management_socio_desk.ejecutar_registrar_cobro_compuesto(
		frm,
		[invoice_row.name],
		[{ mode_of_payment, amount: flt(invoice_row.outstanding_amount) }],
		posting_date
	);
};

club_management_socio_desk.confirmar_registrar_cobro = function (frm, invoice_row) {
	club_management_socio_desk.prompt_modo_y_registrar_cobro(frm, invoice_row);
};

club_management_socio_desk.render_inscripciones = function (frm) {
	if (!frm.fields_dict.actividad || frm.is_new()) {
		return;
	}

	let $panel = frm.fields_dict.actividad.$wrapper
		.closest(".form-section")
		.find(".club-inscripciones-panel");
	if (!$panel.length) {
		$panel = $('<div class="club-inscripciones-panel" style="margin-top: 1rem;"></div>');
		frm.fields_dict.actividad.$wrapper.after($panel);
	}

	$panel.html(`<p class="text-muted small">${__("Cargando inscripciones…")}</p>`);

	frappe.call({
		method: "club_management.members.api.socio_operaciones_desk.list_inscripciones_socio",
		args: { socio: frm.doc.name },
		callback(r) {
			if (r.exc) {
				$panel.empty();
				return;
			}
			const rows = r.message || [];
			if (!rows.length) {
				$panel.html(
					`<div class="text-muted small">${__("Sin inscripciones activas.")}</div>`
				);
				return;
			}

			const $title = $(`<h6 class="mb-2">${__("Inscripciones activas")}</h6>`);
			const $table = $(`
				<table class="table table-bordered table-sm club-inscripciones-table">
					<thead>
						<tr>
							<th>${__("Actividad")}</th>
							<th>${__("Grupo")}</th>
							<th>${__("Equipo")}</th>
							<th>${__("Fecha")}</th>
							<th>${__("Arancel")}</th>
							<th></th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			`);
			const $tbody = $table.find("tbody");

			rows.forEach((row) => {
				const monto_label = row.monto
					? frappe.format(row.monto, { fieldtype: "Currency" })
					: __("Sin arancel");
				const arancel_label = row.item_arancel
					? `${frappe.utils.escape_html(row.item_arancel)} (${monto_label})`
					: monto_label;
				const $tr = $(`
					<tr data-inscripcion="${frappe.utils.escape_html(row.name)}">
						<td>${frappe.utils.escape_html(row.actividad || "")}</td>
						<td>${frappe.utils.escape_html(row.grupo_actividad || "")}</td>
						<td>${frappe.utils.escape_html(row.equipo_actividad || "")}</td>
						<td>${frappe.datetime.str_to_user(row.fecha_inscripcion) || ""}</td>
						<td>${arancel_label}</td>
						<td class="text-right"></td>
					</tr>
				`);
				const $btn = $(`<button type="button" class="btn btn-xs btn-danger">${__("Dar de baja")}</button>`);
				$btn.on("click", () =>
					club_management_socio_desk.confirm_baja_inscripcion(frm, row.name)
				);
				$tr.find("td:last").append($btn);
				$tbody.append($tr);
			});

			$panel.empty().append($title, $table);
		},
	});
};

club_management_socio_desk.confirm_baja_inscripcion = function (frm, inscripcion_name) {
	frappe.confirm(
		__("¿Dar de baja la inscripción {0}?", [inscripcion_name]),
		() => {
			frappe.prompt(
				[
					{
						fieldname: "motivo",
						fieldtype: "Small Text",
						label: __("Motivo"),
					},
				],
				(values) => {
					frappe.call({
						method: "club_management.members.api.socio_operaciones_desk.baja_inscripcion",
						args: {
							inscripcion: inscripcion_name,
							motivo: values.motivo || null,
						},
						freeze: true,
						callback(r) {
							if (!r.exc) {
								frappe.show_alert({
									message: __("Inscripción dada de baja"),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				},
				__("Dar de baja inscripción"),
				__("Confirmar")
			);
		}
	);
};

club_management_socio_desk.actualizar_saldo = function (frm) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.actualizar_saldo_deuda",
		args: { socio: frm.doc.name },
		freeze: true,
		callback(r) {
			if (!r.exc) {
				frm.reload_doc();
			}
		},
	});
};

club_management_socio_desk.render_deuda_pendiente = function (frm) {
	if (!frm.fields_dict.saldo_deuda || frm.is_new()) {
		return;
	}

	let $panel = frm.fields_dict.saldo_deuda.$wrapper
		.closest(".form-section")
		.find(".club-deuda-pendiente-panel");
	if (!$panel.length) {
		$panel = $(
			'<div class="club-deuda-pendiente-panel" style="margin: 1rem 0; clear: both;"></div>'
		);
		frm.fields_dict.saldo_deuda.$wrapper.after($panel);
	}

	$panel.html(`<p class="text-muted small">${__("Cargando deuda pendiente…")}</p>`);

	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_detalle_deuda",
		args: { socio: frm.doc.name },
		callback(r) {
			if (r.exc) {
				$panel.html(
					`<div class="text-danger small">${__("No se pudo cargar el detalle de deuda.")}</div>`
				);
				return;
			}
			const data = r.message || {};
			const facturas = data.facturas || [];
			const cargos = data.cargos_pendientes || [];
			const saldo = flt(data.saldo_deuda);

			if (!saldo && !facturas.length && !cargos.length) {
				$panel.html(
					`<div class="text-muted small">${__("Sin deuda pendiente.")}</div>`
				);
				return;
			}

			const saldo_label = frappe.format(saldo, { fieldtype: "Currency" });
			const $title = $(`<h6 class="mb-2">${__("Detalle de deuda")} — ${saldo_label}</h6>`);
			const $table = $(`
				<table class="table table-bordered table-sm club-deuda-pendiente-table">
					<thead>
						<tr>
							<th>${__("Concepto")}</th>
							<th>${__("Período")}</th>
							<th>${__("Tipo")}</th>
							<th>${__("Monto")}</th>
							<th></th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			`);
			const $tbody = $table.find("tbody");

			facturas.forEach((factura) => {
				const lineas = factura.lineas || [];
				const periodo = frappe.utils.escape_html(factura.periodo_cobro || "—");
				if (!lineas.length) {
					const monto = frappe.format(factura.outstanding_amount, { fieldtype: "Currency" });
					$tbody.append(`
						<tr>
							<td>${frappe.utils.escape_html(factura.name)}</td>
							<td>${periodo}</td>
							<td>${__("Factura")}</td>
							<td>${monto}</td>
							<td></td>
						</tr>
					`);
					return;
				}
				lineas.forEach((linea, idx) => {
					const monto = frappe.format(linea.monto, { fieldtype: "Currency" });
					const concepto =
						idx === 0
							? `${frappe.utils.escape_html(factura.name)} — ${frappe.utils.escape_html(linea.concepto)}`
							: frappe.utils.escape_html(linea.concepto);
					$tbody.append(`
						<tr>
							<td>${concepto}</td>
							<td>${idx === 0 ? periodo : ""}</td>
							<td>${__("Factura")}</td>
							<td>${monto}</td>
							<td></td>
						</tr>
					`);
				});
			});

			cargos.forEach((cargo) => {
				const monto = frappe.format(cargo.monto, { fieldtype: "Currency" });
				const es_recurrente = cargo.modo_cobro === "Recurrente";
				const tipo = es_recurrente
					? __("Cargo extra recurrente (sin factura de este mes)")
					: __("Cargo extra único sin facturar");
				const $tr = $(`
					<tr>
						<td>${frappe.utils.escape_html(cargo.titulo || cargo.name)}</td>
						<td>—</td>
						<td>${tipo}</td>
						<td>${monto}</td>
					</tr>
				`);
				const $td = $("<td></td>");
				const $btn = $(
					`<button type="button" class="btn btn-xs btn-primary">${
						es_recurrente ? __("Facturar este mes") : __("Facturar")
					}</button>`
				);
				$btn.on("click", () => {
					const method = es_recurrente
						? "club_management.members.api.cargo_extra_desk.facturar_mes_corriente"
						: "club_management.members.api.cobranza_desk.facturar_cargo_socio";
					frappe.call({
						method,
						args: { cargo: cargo.name },
						freeze: true,
						callback(res) {
							if (res.exc || !res.message) return;
							frm.reload_doc();
							const invs =
								res.message.sales_invoices ||
								(res.message.sales_invoice ? [res.message.sales_invoice] : []);
							if (!invs.length) {
								frappe.msgprint(__("No se generó factura (el período ya estaba facturado)."));
								return;
							}
							frappe.confirm(__("¿Registrar cobro ahora?"), () => {
								frappe.call({
									method: "club_management.members.api.cobranza_desk.list_facturas_pendientes",
									args: { socio: frm.doc.name },
									callback(pend) {
										if (pend.exc) return;
										const wanted = new Set(invs);
										const rows = (pend.message || []).filter((row) =>
											wanted.has(row.name)
										);
										if (!rows.length) return;
										club_management_socio_desk.prompt_cobro_multi_factura(frm, rows);
									},
								});
							});
						},
					});
				});
				$td.append($btn);
				$tr.append($td);
				$tbody.append($tr);
			});

			$panel.empty().append($title, $table);
		},
	});
};

club_management_socio_desk.render_historial_pagos = function (frm) {
	if (!frm.fields_dict.saldo_deuda || frm.is_new()) {
		return;
	}

	let $panel = frm.fields_dict.saldo_deuda.$wrapper
		.closest(".form-section")
		.find(".club-historial-pagos-panel");
	if (!$panel.length) {
		$panel = $(
			'<div class="club-historial-pagos-panel" style="margin: 1rem 0; clear: both;"></div>'
		);
		const $deuda = frm.fields_dict.saldo_deuda.$wrapper
			.closest(".form-section")
			.find(".club-deuda-pendiente-panel");
		if ($deuda.length) {
			$deuda.after($panel);
		} else {
			frm.fields_dict.saldo_deuda.$wrapper.after($panel);
		}
	}

	$panel.html(`<p class="text-muted small">${__("Cargando historial de pagos…")}</p>`);

	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_historial_pagos",
		args: { socio: frm.doc.name, limit: 20 },
		callback(r) {
			if (r.exc) {
				$panel.html(
					`<div class="text-danger small">${__("No se pudo cargar el historial de pagos.")}</div>`
				);
				return;
			}
			const rows = r.message || [];
			if (!rows.length) {
				$panel.html(
					`<div class="text-muted small">${__("Sin pagos registrados.")}</div>`
				);
				return;
			}

			const $title = $(`<h6 class="mb-2">${__("Historial de pagos")}</h6>`);
			const $btn = $(
				`<button type="button" class="btn btn-xs btn-default mb-2">${__(
					"Copiar resumen"
				)}</button>`
			);
			const resumen = rows
				.map((row) => {
					const monto = frappe.format(row.paid_amount, { fieldtype: "Currency" });
					const facturas = (row.sales_invoices || []).join(", ");
					return `${row.posting_date} | ${row.mode_of_payment || "-"} | ${monto} | ${facturas} | ${row.payment_entry}`;
				})
				.join("\n");
			$btn.on("click", () => {
				frappe.utils.copy_to_clipboard(resumen);
				frappe.show_alert({ message: __("Resumen copiado"), indicator: "green" });
			});

			const $table = $(`
				<table class="table table-bordered table-sm club-historial-pagos-table">
					<thead>
						<tr>
							<th>${__("Fecha")}</th>
							<th>${__("Medio")}</th>
							<th>${__("Monto")}</th>
							<th>${__("Facturas")}</th>
							<th>${__("Pago")}</th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			`);
			const $tbody = $table.find("tbody");
			rows.forEach((row) => {
				const monto = frappe.format(row.paid_amount, { fieldtype: "Currency" });
				const facturas = frappe.utils.escape_html((row.sales_invoices || []).join(", "));
				$tbody.append(`
					<tr>
						<td>${frappe.utils.escape_html(String(row.posting_date || ""))}</td>
						<td>${frappe.utils.escape_html(row.mode_of_payment || "")}</td>
						<td>${monto}</td>
						<td>${facturas}</td>
						<td><a href="/app/payment-entry/${encodeURIComponent(row.payment_entry)}">${frappe.utils.escape_html(
							row.payment_entry
						)}</a></td>
					</tr>
				`);
			});
			$panel.empty().append($title, $btn, $table);
		},
	});
};
