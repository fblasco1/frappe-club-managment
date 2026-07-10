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
	},
	categoria(frm) {
		if (
			!frm.is_new() &&
			(frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager"))
		) {
			club_management_socio_desk.relax_validacion_edicion_secretaria(frm);
		}
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
	if (["Activo", "Moroso", "Suspendido", "Pendiente de Pago", "Pendiente de Inscripción"].includes(estado)) {
		frm.add_custom_button(
			__("Dar de baja"),
			() => club_management_socio_desk.prompt_motivo(frm, "dar_baja", { require_motivo: true }),
			group
		);
	}
	if (estado !== "Baja") {
		frm.add_custom_button(__("Crear beca"), () => club_management_socio_desk.crear_beca(frm), group);
	}

	const cobranza = __("Cobranza manual");
	frm.add_custom_button(
		__("Nuevo cargo extra"),
		() => club_management_socio_desk.nuevo_cargo_extra(frm),
		cobranza
	);
	frm.add_custom_button(__("Generar cargo"), () => club_management_socio_desk.generar_cargo(frm), cobranza);
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
			{ fieldname: "selecciones_json", fieldtype: "Small Text", label: __("Selecciones"), read_only: 1 },
		],
		primary_action_label: __("Agregar"),
		primary_action() {
			const vals = d.get_values();
			if (!vals.actividad) return;
			let rows = [];
			try {
				rows = vals.selecciones_json ? JSON.parse(vals.selecciones_json) : [];
			} catch (e) {
				rows = [];
			}
			rows.push({
				actividad: vals.actividad,
				grupo: vals.grupo || null,
				equipo: vals.equipo || null,
			});
			d.set_value("selecciones_json", JSON.stringify(rows, null, 2));
			d.set_value("actividad", "");
			d.set_value("grupo", "");
			d.set_value("equipo", "");
		},
		secondary_action_label: __("Confirmar inscripción"),
		secondary_action() {
			const vals = d.get_values();
			let selecciones = [];
			try {
				selecciones = vals.selecciones_json ? JSON.parse(vals.selecciones_json) : [];
			} catch (e) {
				frappe.msgprint(__("Selecciones inválidas"));
				return;
			}
			if (!selecciones.length) {
				frappe.msgprint(__("Agregue al menos una actividad"));
				return;
			}
			frappe.call({
				method: "club_management.members.api.socio_operaciones_desk.inscribir_actividades",
				args: { socio: frm.doc.name, selecciones: JSON.stringify(selecciones) },
				freeze: true,
				callback(r) {
					if (!r.exc) {
						d.hide();
						frm.reload_doc();
						frappe.show_alert({ message: __("Inscripción registrada"), indicator: "green" });
					}
				},
			});
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
	frappe.route_options = { socio: frm.doc.name };
	frappe.new_doc("Cargo Socio");
};

club_management_socio_desk.crear_beca = function (frm) {
	frappe.route_options = { socio: frm.doc.name };
	frappe.new_doc("Beca Socio");
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
	frappe.call({
		method: "club_management.members.api.cobranza_desk.generar_cargo",
		args: { socio: frm.doc.name, incluir_actividades: 1 },
		freeze: true,
		callback(r) {
			if (!r.exc && r.message) {
				frappe.msgprint(
					__("Factura {0} — saldo {1}", [
						r.message.sales_invoice,
						frappe.format(r.message.saldo_deuda, { fieldtype: "Currency" }),
					])
				);
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
			if (rows.length === 1) {
				club_management_socio_desk.prompt_modo_y_registrar_cobro(frm, rows[0]);
				return;
			}
			const labels = rows.map((row) => {
				const saldo = frappe.format(row.outstanding_amount, { fieldtype: "Currency" });
				return `${row.name} — ${saldo}`;
			});
			frappe.prompt(
				[
					{
						fieldname: "sales_invoice",
						fieldtype: "Select",
						label: __("Factura pendiente"),
						options: labels.join("\n"),
						reqd: 1,
					},
				],
				(values) => {
					const invoice = (values.sales_invoice || "").split(" — ")[0].trim();
					const row = rows.find((item) => item.name === invoice);
					club_management_socio_desk.prompt_modo_y_registrar_cobro(frm, row || { name: invoice });
				},
				__("Registrar cobro"),
				__("Continuar")
			);
		},
	});
};

club_management_socio_desk.prompt_modo_y_registrar_cobro = function (frm, invoice_row) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_modos_pago_cobranza",
		callback(r) {
			if (r.exc) {
				return;
			}
			const modos = r.message || [];
			const labelToValue = {};
			const options = modos
				.map((row) => {
					labelToValue[row.label] = row.value;
					return row.label;
				})
				.join("\n");
			const saldo_label = frappe.format(invoice_row.outstanding_amount, {
				fieldtype: "Currency",
			});
			frappe.prompt(
				[
					{
						fieldname: "mode_of_payment",
						fieldtype: "Select",
						label: __("Medio de pago"),
						options,
						default: modos[0]?.label,
						reqd: 1,
					},
					{
						fieldname: "posting_date",
						fieldtype: "Date",
						label: __("Fecha de cobro"),
						default: frappe.datetime.get_today(),
						reqd: 1,
					},
				],
				(values) => {
					const mode = labelToValue[values.mode_of_payment] || "Cash";
					club_management_socio_desk.ejecutar_registrar_cobro(
						frm,
						invoice_row,
						mode,
						values.posting_date
					);
				},
				__("Registrar cobro de {0} — {1}", [invoice_row.name, saldo_label]),
				__("Confirmar")
			);
		},
	});
};

club_management_socio_desk.ejecutar_registrar_cobro = function (
	frm,
	invoice_row,
	mode_of_payment,
	posting_date
) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.registrar_cobro",
		args: {
			socio: frm.doc.name,
			sales_invoice: invoice_row.name,
			mode_of_payment,
			posting_date,
		},
		freeze: true,
		callback(res) {
			if (!res.exc && res.message) {
				frappe.show_alert({
					message: __("Cobro {0} registrado", [res.message.payment_entry]),
					indicator: "green",
				});
				if (res.message.recibo && club_management_recibo_pago?.imprimir_despues_cobro) {
					club_management_recibo_pago.imprimir_despues_cobro(res.message.recibo);
				}
				frm.reload_doc();
			}
		},
	});
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
							<th>${__("Tipo")}</th>
							<th>${__("Monto")}</th>
						</tr>
					</thead>
					<tbody></tbody>
				</table>
			`);
			const $tbody = $table.find("tbody");

			facturas.forEach((factura) => {
				const lineas = factura.lineas || [];
				if (!lineas.length) {
					const monto = frappe.format(factura.outstanding_amount, { fieldtype: "Currency" });
					$tbody.append(`
						<tr>
							<td>${frappe.utils.escape_html(factura.name)}</td>
							<td>${__("Factura")}</td>
							<td>${monto}</td>
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
							<td>${__("Factura")}</td>
							<td>${monto}</td>
						</tr>
					`);
				});
			});

			cargos.forEach((cargo) => {
				const monto = frappe.format(cargo.monto, { fieldtype: "Currency" });
				const tipo =
					cargo.modo_cobro === "Recurrente"
						? __("Cargo extra (recurrente, sin facturar en este mes)")
						: __("Cargo extra — usar «Facturar cargo»");
				$tbody.append(`
					<tr>
						<td>${frappe.utils.escape_html(cargo.titulo || cargo.name)}</td>
						<td>${tipo}</td>
						<td>${monto}</td>
					</tr>
				`);
			});

			$panel.empty().append($title, $table);
		},
	});
};
