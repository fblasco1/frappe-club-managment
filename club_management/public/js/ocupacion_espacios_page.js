/* global frappe */

(function () {
	frappe.provide("club_management.ocupacion_espacios_page");

	const ROW_H = 28;
	const WINDOW_START = 8 * 60;

	club_management.ocupacion_espacios_page = {
		page: null,
		_fecha: null,
		_data: null,

		init(page) {
			this.page = page;
			page.main.addClass("club-ocupacion-page");
			this._fecha = frappe.datetime.get_today();
			this._build_toolbar();
			this.load();
		},

		refresh() {
			if (this.page) {
				this.load();
			}
		},

		_build_toolbar() {
			const page = this.page;
			page.set_primary_action(__("Actualizar"), () => this.load(), "refresh");

			const $ctrl = $(`
				<div class="club-ocupacion-toolbar">
					<label class="club-ocupacion-fecha-label">${__("Fecha")}</label>
					<input type="date" class="form-control form-control-sm club-ocupacion-fecha">
					<span class="club-ocupacion-dia-label text-muted"></span>
					<button type="button" class="btn btn-sm btn-secondary club-ocupacion-sync-febamba">
						${__("Sincronizar FeBAMBA")}
					</button>
					<button type="button" class="btn btn-sm btn-secondary club-ocupacion-sync-fmv">
						${__("Sincronizar FMV")}
					</button>
					<button type="button" class="btn btn-sm btn-secondary club-ocupacion-import-excel">
						${__("Importar Excel ligas")}
					</button>
				</div>
			`);
			page.main.prepend($ctrl);
			$ctrl.find(".club-ocupacion-fecha").val(this._fecha).on("change", (e) => {
				this._fecha = e.target.value;
				this.load();
			});
			$ctrl.find(".club-ocupacion-sync-febamba").on("click", () => this.sync_febamba());
			$ctrl.find(".club-ocupacion-sync-fmv").on("click", () => this.sync_fmv());
			$ctrl.find(".club-ocupacion-import-excel").on("click", () => this.import_excel_ligas());
		},

		sync_febamba() {
			frappe.call({
				method: "club_management.spaces.api.fixtures_desk.sync_fixtures_febamba",
				args: { cancel_missing: 1 },
				freeze: true,
				freeze_message: __("Sincronizando fixture FeBAMBA GES…"),
				callback: (r) => {
					this._show_fixture_report(r.message || {});
					this.load();
				},
			});
		},

		sync_fmv() {
			frappe.call({
				method: "club_management.spaces.api.fixtures_desk.sync_fixtures_fmv",
				args: { cancel_missing: 1 },
				freeze: true,
				freeze_message: __("Sincronizando fixture FMV Vóley…"),
				callback: (r) => {
					this._show_fixture_report(r.message || {});
					this.load();
				},
			});
		},

		import_excel_ligas() {
			const templateUrl =
				"/api/method/club_management.spaces.api.fixtures_desk.download_fixtures_excel_template";
			const dialog = new frappe.ui.Dialog({
				title: __("Importar Excel de fixtures"),
				fields: [
					{
						fieldtype: "HTML",
						options: `
							<p>${__("Usá la plantilla canónica para preparar los partidos de la liga.")}</p>
							<p>
								<a class="btn btn-default btn-sm" href="${templateUrl}" target="_blank">
									${__("Descargar plantilla Excel")}
								</a>
							</p>
							<p class="text-muted small">${__(
								"Reemplazá la fila de ejemplo. SICLUB genera automáticamente el origen, el identificador y el equipo."
							)}</p>
						`,
					},
				],
				primary_action_label: __("Seleccionar Excel"),
				primary_action: () => {
					dialog.hide();
					this._open_excel_uploader();
				},
			});
			dialog.show();
		},

		_open_excel_uploader() {
			new frappe.ui.FileUploader({
				restrictions: { allowed_file_types: [".xlsx"] },
				on_success: (file_doc) => {
					const file_url = file_doc.file_url;
					frappe.call({
						method: "club_management.spaces.api.fixtures_desk.preview_fixtures_excel",
						args: { file_url },
						freeze: true,
						freeze_message: __("Validando Excel…"),
						callback: (r) => {
							const preview = r.message || {};
							const ok = (preview.filas_ok || []).length;
							const err = (preview.errores || []).length;
							const msg = [
								__("Filas OK: {0}", [ok]),
								__("Errores: {0}", [err]),
							].join(" · ");
							frappe.confirm(
								`${msg}<br><br>${__("¿Aplicar importación idempotente?")}`,
								() => {
									frappe.call({
										method: "club_management.spaces.api.fixtures_desk.apply_fixtures_excel",
										args: { file_url, cancel_missing: 0 },
										freeze: true,
										freeze_message: __("Importando partidos…"),
										callback: (res) => {
											this._show_fixture_report(res.message || {});
											this.load();
										},
									});
								}
							);
						},
					});
				},
			});
		},

		_show_fixture_report(rep) {
			const parts = [
				__("Creados: {0}", [rep.creados || 0]),
				__("Actualizados: {0}", [rep.actualizados || 0]),
				__("Cancelados: {0}", [rep.cancelados || 0]),
			];
			if ((rep.superposiciones || []).length) {
				parts.push(__("Superposiciones: {0}", [rep.superposiciones.length]));
			}
			if ((rep.omitidos || []).length) {
				parts.push(__("Omitidos: {0}", [rep.omitidos.length]));
			}
			if ((rep.errores || []).length) {
				parts.push(__("Errores: {0}", [rep.errores.length]));
			}
			frappe.show_alert({
				message: parts.join(" · "),
				indicator: rep.errores?.length ? "orange" : "green",
			});
			if ((rep.superposiciones || []).length) {
				frappe.msgprint({
					title: __("Superposiciones a revisar"),
					message: `<ul>${rep.superposiciones
						.slice(0, 15)
						.map((s) => `<li>${frappe.utils.escape_html(s)}</li>`)
						.join("")}</ul>`,
					indicator: "orange",
				});
			}
			const issues = [...(rep.errores || []), ...(rep.omitidos || [])];
			if (issues.length) {
				frappe.msgprint({
					title: __("Filas no importadas"),
					message: `<ul>${issues
						.slice(0, 30)
						.map((item) => `<li>${frappe.utils.escape_html(item)}</li>`)
						.join("")}</ul>`,
					indicator: "orange",
				});
			}
		},

		load() {
			const fecha = this._fecha || frappe.datetime.get_today();
			frappe.call({
				method: "club_management.spaces.api.ocupacion_dashboard.get_ocupacion_dashboard",
				args: { fecha },
				freeze: true,
				freeze_message: __("Cargando ocupación…"),
				callback: (r) => {
					if (!r.message) {
						return;
					}
					this._data = r.message;
					this._fecha = r.message.fecha;
					this.page.main.find(".club-ocupacion-fecha").val(this._fecha);
					this.page.main
						.find(".club-ocupacion-dia-label")
						.text((r.message.dia_semana || "").toUpperCase());
					this.render();
				},
			});
		},

		render() {
			const data = this._data;
			if (!data) {
				return;
			}

			const $host = this.page.main.find(".club-ocupacion-grid-host");
			if (!$host.length) {
				this.page.main.append('<div class="club-ocupacion-grid-host"></div>');
			}
			const $gridHost = this.page.main.find(".club-ocupacion-grid-host");

			const espacios = data.espacios || [];
			const slots = data.slots || [];
			const bloques = data.bloques || [];
			const totalH = slots.length * ROW_H;

			if (!espacios.length) {
				$gridHost.html(
					`<p class="text-muted">${__("No hay espacios habilitados. Creá espacios en el catálogo.")}</p>`
				);
				return;
			}

			const legend = (data.leyenda || [])
				.map(
					(l) =>
						`<span class="club-ocupacion-legend-item">
							<span class="club-ocupacion-swatch" style="background:${frappe.utils.escape_html(l.color)}"></span>
							${frappe.utils.escape_html(l.label)}
						</span>`
				)
				.join("");

			const superAlerts = (data.superposiciones || [])
				.map(
					(s) =>
						`<li class="club-ocupacion-superposicion-item">${frappe.utils.escape_html(s)}</li>`
				)
				.join("");
			const superHtml = superAlerts
				? `<div class="club-ocupacion-superposiciones alert alert-warning">
					<strong>${__("Superposiciones a corregir")}</strong>
					<ul class="club-ocupacion-superposiciones-list">${superAlerts}</ul>
				</div>`
				: "";

			const headerCols = espacios
				.map(
					(e) =>
						`<th class="club-ocupacion-col-head" title="${frappe.utils.escape_html(e.tipo || "")}">
							${frappe.utils.escape_html(e.titulo_planilla || e.titulo || e.name)}
						</th>`
				)
				.join("");

			const timeLabels = slots
				.map(
					(s, i) =>
						`<div class="club-ocupacion-time-slot" style="top:${i * ROW_H}px;height:${ROW_H}px">${frappe.utils.escape_html(s)}</div>`
				)
				.join("");

			const byEspacio = {};
			for (const b of bloques) {
				const key = b.espacio;
				if (!byEspacio[key]) {
					byEspacio[key] = [];
				}
				byEspacio[key].push(b);
			}

			const bodyCols = espacios
				.map((e) => {
					const list = byEspacio[e.name] || [];
					const blocksHtml = list
						.map((b, idx) => {
							const top = ((b.inicio_min - WINDOW_START) / 30) * ROW_H;
							const height = Math.max(
								((b.fin_min - b.inicio_min) / 30) * ROW_H,
								ROW_H * 0.6
							);
							const stagger = (idx % 4) * 6;
							const title = frappe.utils.escape_html(b.titulo || "");
							const color = frappe.utils.escape_html(b.color || "#d0d7de");
							const ref = frappe.utils.escape_html(b.ref || "");
							const source = frappe.utils.escape_html(b.source || "");
							const espacio = frappe.utils.escape_html(b.espacio || "");
							const horarioRow = frappe.utils.escape_html(b.horario_row || b.ref || "");
							const inicio = frappe.utils.escape_html(b.inicio || "");
							const fin = frappe.utils.escape_html(b.fin || "");
							const superClass = b.superposicion ? " club-ocupacion-block--superposicion" : "";
							const inicioMin = b.inicio_min;
							const finMin = b.fin_min;
							return `<div class="club-ocupacion-block${superClass}"
								data-source="${source}" data-ref="${ref}"
								data-espacio="${espacio}" data-horario-row="${horarioRow}"
								data-inicio="${inicio}" data-fin="${fin}" data-titulo="${title}"
								data-inicio-min="${inicioMin}" data-fin-min="${finMin}"
								data-superposicion="${b.superposicion ? 1 : 0}"
								style="top:${top}px;height:${height}px;left:calc(4px + ${stagger}px);right:4px;background:${color}"
								title="${title}">
								<span class="club-ocupacion-block-text">${title}</span>
							</div>`;
						})
						.join("");
					return `<td class="club-ocupacion-col-body">
						<div class="club-ocupacion-col-canvas" style="height:${totalH}px">
							${slots
								.map(
									(_, i) =>
										`<div class="club-ocupacion-gridline" style="top:${i * ROW_H}px;height:${ROW_H}px"></div>`
								)
								.join("")}
							${blocksHtml}
						</div>
					</td>`;
				})
				.join("");

			$gridHost.html(`
				<div class="club-ocupacion-legend">${legend}</div>
				${superHtml}
				<div class="club-ocupacion-scroll">
					<table class="club-ocupacion-table">
						<thead>
							<tr>
								<th class="club-ocupacion-hora-head">${__("HORA")}</th>
								${headerCols}
							</tr>
						</thead>
						<tbody>
							<tr>
								<td class="club-ocupacion-hora-body">
									<div class="club-ocupacion-time-col" style="height:${totalH}px">${timeLabels}</div>
								</td>
								${bodyCols}
							</tr>
						</tbody>
					</table>
				</div>
			`);

			$gridHost.find(".club-ocupacion-block").on("click", (ev) => {
				const $el = $(ev.currentTarget);
				const cluster = this._find_overlap_cluster($el);
				if (cluster.length > 1) {
					this.open_superposicion_picker(cluster);
					return;
				}
				this._act_on_block($el);
			});
		},

		_block_from_element($el) {
			return {
				source: $el.data("source"),
				ref: $el.data("ref"),
				espacio: $el.data("espacio"),
				horario_row: $el.data("horario-row") || $el.data("ref"),
				inicio: $el.data("inicio"),
				fin: $el.data("fin"),
				titulo: $el.data("titulo") || "",
				inicio_min: Number($el.data("inicio-min")),
				fin_min: Number($el.data("fin-min")),
			};
		},

		_find_overlap_cluster($el) {
			const clicked = this._block_from_element($el);
			const bloques = (this._data && this._data.bloques) || [];
			return bloques.filter(
				(b) =>
					b.espacio === clicked.espacio &&
					b.inicio_min < clicked.fin_min &&
					clicked.inicio_min < b.fin_min
			);
		},

		_label_for_block(block) {
			const tipo = block.categoria || block.tipo || block.tipo_sesion || __("Evento");
			return `${block.titulo || __("Sin título")} (${block.inicio}–${block.fin}) — ${tipo}`;
		},

		open_superposicion_picker(blocks) {
			const page = this;
			const rows = blocks
				.map(
					(b, idx) => `<tr class="club-ocupacion-pick-row" data-idx="${idx}">
						<td><input type="radio" name="club_ocupacion_pick" value="${idx}" ${idx === 0 ? "checked" : ""}></td>
						<td>${frappe.utils.escape_html(page._label_for_block(b))}</td>
					</tr>`
				)
				.join("");
			const d = new frappe.ui.Dialog({
				title: __("Superposición — elegir evento"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"Hay varios eventos solapados en este horario. Elegí cuál querés modificar."
						)}</p>
						<table class="table table-bordered table-sm club-ocupacion-pick-table">
							<thead><tr><th></th><th>${__("Evento")}</th></tr></thead>
							<tbody>${rows}</tbody>
						</table>`,
					},
				],
				primary_action_label: __("Continuar"),
				primary_action() {
					const idx = Number(d.$wrapper.find('input[name="club_ocupacion_pick"]:checked').val());
					const block = blocks[idx];
					if (!block) {
						return;
					}
					d.hide();
					page._act_on_block_data(block);
				},
			});
			d.$wrapper.find(".club-ocupacion-pick-row").on("click", function onPickRow() {
				$(this).find('input[type="radio"]').prop("checked", true);
			});
			d.show();
		},

		_act_on_block($el) {
			this._act_on_block_data(this._block_from_element($el));
		},

		_act_on_block_data(block) {
			const source = block.source;
			const ref = block.ref;
			if (source === "reserva" && ref) {
				this.open_reserva_dia_dialog(block);
				return;
			}
			if (source === "excepcion" && ref) {
				frappe.set_route("Form", "Excepcion Horario Dia", ref);
				return;
			}
			if (source === "horario") {
				this.open_horario_dia_dialog({
					espacio: block.espacio,
					horario_row: block.horario_row || ref,
					inicio: block.inicio,
					fin: block.fin,
					titulo: block.titulo || "",
				});
			}
		},

		_to_time_input(hhmm) {
			if (!hhmm) {
				return "00:00:00";
			}
			const s = String(hhmm);
			return s.length === 5 ? `${s}:00` : s;
		},

		open_horario_dia_dialog(block) {
			const page = this;
			const d = new frappe.ui.Dialog({
				title: __("Entrenamiento — ajuste del día"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"No modifica la grilla semanal. Solo afecta el {0}.",
							[page._fecha]
						)}</p>
							<p><strong>${frappe.utils.escape_html(block.titulo || "")}</strong></p>`,
					},
					{
						fieldname: "accion",
						label: __("Acción"),
						fieldtype: "Select",
						options: "Reubicar\nSuspender",
						reqd: 1,
						default: "Reubicar",
						change() {
							const accion = d.get_value("accion");
							const suspend = accion === "Suspender";
							d.toggle_display("espacio_destino", !suspend);
							d.toggle_display("hora_desde", !suspend);
							d.toggle_display("hora_hasta", !suspend);
							d.get_primary_btn().text(
								suspend ? __("Suspender solo este día") : __("Guardar reubicación")
							);
						},
					},
					{
						fieldname: "espacio_destino",
						label: __("Espacio destino"),
						fieldtype: "Link",
						options: "Espacio",
						reqd: 1,
						default: block.espacio,
					},
					{
						fieldname: "hora_desde",
						label: __("Hora desde"),
						fieldtype: "Time",
						reqd: 1,
						default: page._to_time_input(block.inicio),
					},
					{
						fieldname: "hora_hasta",
						label: __("Hora hasta"),
						fieldtype: "Time",
						reqd: 1,
						default: page._to_time_input(block.fin),
					},
					{
						fieldname: "motivo",
						label: __("Motivo"),
						fieldtype: "Small Text",
						default: __("Ajuste por superposición / cronograma del día"),
					},
				],
				primary_action_label: __("Guardar reubicación"),
				primary_action(values) {
					const accion = values.accion || "Reubicar";
					const method =
						accion === "Suspender"
							? "club_management.spaces.api.excepcion_horario.suspender_horario_dia"
							: "club_management.spaces.api.excepcion_horario.reubicar_horario_dia";
					const args =
						accion === "Suspender"
							? {
									fecha: page._fecha,
									espacio_origen: block.espacio,
									horario_row: block.horario_row,
									motivo: values.motivo,
								}
							: {
									fecha: page._fecha,
									espacio_origen: block.espacio,
									horario_row: block.horario_row,
									espacio_destino: values.espacio_destino,
									hora_desde: values.hora_desde,
									hora_hasta: values.hora_hasta,
									motivo: values.motivo,
								};
					frappe.call({
						method,
						args,
						freeze: true,
						callback(r) {
							if (r.message?.name) {
								frappe.show_alert({
									message:
										accion === "Suspender"
											? __("Entrenamiento suspendido para este día")
											: __("Entrenamiento reubicado para este día"),
									indicator: "green",
								});
								d.hide();
								page.load();
							}
						},
					});
				},
			});
			d.show();
		},

		open_reserva_dia_dialog(block) {
			const page = this;
			const d = new frappe.ui.Dialog({
				title: __("Reserva / evento — ajuste del día"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"La reserva base no se cancela. Solo deja de ocupar el espacio el {0}.",
							[page._fecha]
						)}</p>
							<p><strong>${frappe.utils.escape_html(block.titulo || "")}</strong></p>`,
					},
					{
						fieldname: "motivo",
						label: __("Motivo de suspensión"),
						fieldtype: "Small Text",
						default: __("Suspendido por coordinación"),
					},
				],
				primary_action_label: __("Suspender solo este día"),
				primary_action(values) {
					frappe.call({
						method: "club_management.spaces.api.suspension_reserva.suspender_reserva_dia",
						args: {
							fecha: page._fecha,
							reserva_espacio: block.ref,
							motivo: values.motivo,
						},
						freeze: true,
						callback(r) {
							if (r.message?.name) {
								frappe.show_alert({
									message: __("Reserva suspendida para este día"),
									indicator: "green",
								});
								d.hide();
								page.load();
							}
						},
					});
				},
				secondary_action_label: __("Abrir formulario"),
				secondary_action() {
					d.hide();
					frappe.set_route("Form", "Reserva Espacio", block.ref);
				},
			});
			d.show();
		},
	};
})();
