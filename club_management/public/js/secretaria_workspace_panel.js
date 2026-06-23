/* global frappe */

(function () {

	frappe.provide("club_management.secretaria_panel");



	const SECRETARIA_WORKSPACE_NAME = "Secretaría";

	const PANEL_ID = "club-secretaria-lists";



	club_management.secretaria_panel = {

		_refresh_timer: null,



		schedule_refresh() {

			clearTimeout(this._refresh_timer);

			this._refresh_timer = setTimeout(() => this.refresh(), 400);

		},



		is_secretaria_workspace() {

			const nav = club_management.club_desk_navigation;

			if (nav?.get_club_workspace_name) {

				return nav.get_club_workspace_name() === SECRETARIA_WORKSPACE_NAME;

			}

			return frappe.workspace?._page?.name === SECRETARIA_WORKSPACE_NAME;

		},



		get_mount_parent() {
			const ws = frappe.workspace;
			if (!ws || !ws.body) return null;
			ws.body.addClass("club-secretaria-workspace-body");
			ws.body
				.parents(".layout-main-section-wrapper, .layout-main-section, .page-body, .container")
				.addClass("club-secretaria-workspace-body");
			const container = ws.body.find(".editor-js-container");
			if (!container.length) return null;
			container.addClass("club-secretaria-workspace");
			return container;
		},



		clear_mount() {
			$(`#${PANEL_ID}`).remove();
			const ws = frappe.workspace;
			ws?.body?.find(".editor-js-container")?.removeClass("club-secretaria-workspace");
			ws?.body?.removeClass("club-secretaria-workspace-body");
			ws?.body
				?.parents(".layout-main-section-wrapper, .layout-main-section, .page-body, .container")
				?.removeClass("club-secretaria-workspace-body");
		},



		ensure_mount_point($parent) {

			if ($(`#${PANEL_ID}`).length) {

				return $(`#${PANEL_ID}`);

			}

			const $panel = $(`<div id="${PANEL_ID}" class="club-secretaria-lists"></div>`);

			$parent.prepend($panel);

			return $panel;

		},



		render_loading($panel) {

			$panel.html(`<div class="text-muted">${__("Cargando panel…")}</div>`);

		},



		render_delta(delta) {
			const value = Number(delta) || 0;
			if (value > 0) {
				return `<span class="club-secretaria-kpi-delta is-up" style="color:#059669">▲ +${value} ${__(
					"vs mes anterior"
				)}</span>`;
			}
			if (value < 0) {
				return `<span class="club-secretaria-kpi-delta is-down" style="color:#dc2626">▼ ${value} ${__(
					"vs mes anterior"
				)}</span>`;
			}
			return `<span class="club-secretaria-kpi-delta is-flat">= 0 ${__("vs mes anterior")}</span>`;
		},



		render_altas_bajas(altasBajas) {
			const altas = Number(altasBajas?.altas) || 0;
			const bajas = Number(altasBajas?.bajas) || 0;
			return `<span class="club-secretaria-altas-bajas">+${altas} / -${bajas}</span>`;
		},

		render_kpi_cards(metricas) {
			const socios = metricas.socios || {};
			const recaudacion = metricas.recaudacion || {};
			const verMas = metricas.ver_mas || {};
			const cuotas = recaudacion.cuotas_sociales || {};
			const mora = socios.mora_1_3 || {};
			const moraDeudaLabel =
				mora.monto_label || frappe.format(mora.monto || 0, { fieldtype: "Currency" });

			return `
				<div class="club-secretaria-kpi-grid">
					<div class="club-secretaria-kpi-card">
						<p class="club-secretaria-kpi-title">${__("Total socios activos")}</p>
						<div class="club-secretaria-kpi-value">${socios.total ?? 0}</div>
						<div class="club-secretaria-kpi-footer">
							${this.render_delta(socios.delta_mes)}
							${this.render_ver_mas_btn(verMas.socios_total_doctype, verMas.socios_total_filters)}
						</div>
					</div>
					<div class="club-secretaria-kpi-card">
						<p class="club-secretaria-kpi-title">${__("Tasa de cobrabilidad del mes")}</p>
						<div class="club-secretaria-kpi-value club-secretaria-kpi-value--pct">${cuotas.porcentaje ?? 0}%</div>
						<span class="text-muted small">${__("Mes")} ${frappe.utils.escape_html(recaudacion.periodo || "")}</span>
					</div>
					<div class="club-secretaria-kpi-card">
						<p class="club-secretaria-kpi-title">${__("Altas vs bajas (mes)")}</p>
						<div class="club-secretaria-kpi-value club-secretaria-kpi-value--ratio">
							${this.render_altas_bajas(socios.altas_bajas)}
						</div>
					</div>
					<div class="club-secretaria-kpi-card club-secretaria-kpi-card--morosos">
						<p class="club-secretaria-kpi-title">${__("Socios en mora (1–3 meses)")}</p>
						<div class="club-secretaria-kpi-value">${mora.cantidad ?? 0}</div>
						<p class="club-secretaria-kpi-deuda">${frappe.utils.escape_html(moraDeudaLabel)}</p>
						<div class="club-secretaria-kpi-footer">
							${this.render_ver_mas_btn(verMas.socios_deuda_doctype, verMas.socios_deuda_filters)}
						</div>
					</div>
				</div>
			`;
		},

		has_segmentos_chart(segmentos) {
			const s = segmentos || {};
			return (s.total || 0) > 0;
		},

		render_charts(metricas) {
			const socios = metricas.socios || {};
			const tendencia = metricas.tendencia_recaudacion || {};
			const medios = metricas.medios_pago || {};
			const showTrend = tendencia.disponible && (tendencia.meses || []).length;
			const showSegmentos = this.has_segmentos_chart(socios.segmentos);
			const showMedios =
				medios.disponible &&
				(medios.debito_automatico ||
					medios.efectivo_pos ||
					medios.transferencia ||
					medios.otros);
			if (!showTrend && !showSegmentos && !showMedios) {
				return "";
			}
			const trendHtml = showTrend
				? `<div class="club-secretaria-charts-row club-secretaria-charts-row--trend">
					<div class="club-secretaria-chart-card club-secretaria-chart-card--wide">
						<h6>${__("Tendencia de recaudación")}</h6>
						<div class="club-secretaria-chart-trend"></div>
					</div>
				</div>`
				: "";
			const secondaryHtml =
				showSegmentos || showMedios
					? `<div class="club-secretaria-charts-row club-secretaria-charts-row--secondary">
					${showSegmentos ? `<div class="club-secretaria-chart-card"><h6>${__("Socios por categoría")}</h6><div class="club-secretaria-chart-segmentos"></div></div>` : ""}
					${showMedios ? `<div class="club-secretaria-chart-card club-secretaria-chart-card--medios"><h6>${__("Medios de pago del mes")}</h6><div class="club-secretaria-chart-medios"></div></div>` : ""}
				</div>`
					: "";
			return `${trendHtml}${secondaryHtml}`;
		},

		mount_charts($panel, metricas) {
			this._destroy_charts();
			const socios = metricas.socios || {};
			const tendencia = metricas.tendencia_recaudacion || {};
			const medios = metricas.medios_pago || {};
			const segmentos = socios.segmentos || {};
			const $segmentos = $panel.find(".club-secretaria-chart-segmentos");
			if ($segmentos.length && this.has_segmentos_chart(segmentos)) {
				this._chart_segmentos = new frappe.Chart($segmentos[0], {
					type: "bar",
					height: 240,
					colors: ["#5e64ff"],
					data: {
						labels: [
							__("Mayores"),
							__("Menores"),
							__("Adherentes"),
							__("Jubilados"),
						],
						datasets: [
							{
								name: __("Socios"),
								values: [
									segmentos.mayores || 0,
									segmentos.menores || 0,
									segmentos.adherentes || 0,
									segmentos.jubilados || 0,
								],
							},
						],
					},
					barOptions: { spaceRatio: 0.45 },
					axisOptions: { shortenYAxisNumbers: 1 },
				});
			}
			const $trend = $panel.find(".club-secretaria-chart-trend");
			if ($trend.length && tendencia.meses?.length) {
				this._chart_trend = new frappe.Chart($trend[0], {
					type: "line",
					height: 220,
					colors: ["#29cd42", "#7575ff"],
					data: {
						labels: tendencia.meses.map((row) => row.periodo),
						datasets: [
							{ name: __("Recaudado"), values: tendencia.meses.map((r) => r.recaudado) },
							{ name: __("Emitido"), values: tendencia.meses.map((r) => r.emitido) },
						],
					},
					truncateLegends: 1,
					axisOptions: { shortenYAxisNumbers: 1 },
				});
			}
			const $medios = $panel.find(".club-secretaria-chart-medios");
			if ($medios.length && medios.disponible) {
				this._chart_medios = new frappe.Chart($medios[0], {
					type: "donut",
					height: 260,
					colors: ["#5e64ff", "#29cd42", "#f39c12", "#95a5a6"],
					data: {
						labels: [
							__("Débito automático"),
							__("Efectivo / POS"),
							__("Transferencia"),
							__("Otros"),
						],
						datasets: [
							{
								values: [
									medios.debito_automatico || 0,
									medios.efectivo_pos || 0,
									medios.transferencia || 0,
									medios.otros || 0,
								],
							},
						],
					},
				});
			}
		},

		_destroy_charts() {
			this._chart_trend = null;
			this._chart_segmentos = null;
			this._chart_medios = null;
		},

		render_solicitudes_table(solicitudes, verMas) {
			const rows = solicitudes || [];
			if (!rows.length) {
				return `
					<div class="club-secretaria-list-card">
						<div class="club-secretaria-list-header">
							<span class="club-secretaria-list-icon">📋</span>
							<h5 class="mb-0">${__("Solicitudes de socios")}</h5>
						</div>
						<p class="text-muted mb-0">${__("No hay solicitudes pendientes.")}</p>
					</div>
				`;
			}
			const body = rows
				.map(
					(row) => `
				<tr class="club-secretaria-solicitud-row" data-name="${frappe.utils.escape_html(row.name)}" role="button" tabindex="0">
					<td>${frappe.utils.escape_html(row.titulo)}</td>
					<td>${frappe.utils.escape_html(row.dni)}</td>
					<td>${frappe.utils.escape_html(row.estado_label || "")}</td>
					<td>${frappe.utils.escape_html(row.fecha_label || "")}</td>
				</tr>`
				)
				.join("");
			return `
				<div class="club-secretaria-list-card">
					<div class="club-secretaria-list-header">
						<span class="club-secretaria-list-icon">📋</span>
						<h5 class="mb-0">${__("Solicitudes de socios")}</h5>
						<div class="ms-auto">
							${this.render_ver_mas_btn(verMas.solicitudes_doctype, verMas.solicitudes_filters)}
						</div>
					</div>
					<div class="table-responsive club-secretaria-solicitudes-table-wrap">
						<table class="table table-sm mb-0 club-secretaria-solicitudes-table">
							<thead>
								<tr>
									<th>${__("Nombre")}</th>
									<th>${__("DNI")}</th>
									<th>${__("Estado")}</th>
									<th>${__("Ingreso")}</th>
								</tr>
							</thead>
							<tbody>${body}</tbody>
						</table>
					</div>
				</div>
			`;
		},

		render_quick_actions() {
			return `
				<div class="club-secretaria-quick-actions">
					<button type="button" class="btn btn-primary club-secretaria-nuevo-socio">
						${__("+ Nueva alta de socio")}
					</button>
					<button type="button" class="btn btn-secondary club-secretaria-cobranza">
						${__("Emitir cupón / Registrar cobro")}
					</button>
					<button type="button" class="btn btn-default" disabled title="${__("Próximamente")}">
						${__("Enviar recordatorio de deuda masivo")}
					</button>
				</div>
			`;
		},



		render_lists($panel, data) {
			const metricas = data.metricas || {};
			const verMas = metricas.ver_mas || {};

			$panel.html(`
				${this.render_quick_actions()}
				${this.render_kpi_cards(metricas)}
				${this.render_charts(metricas)}
				${this.render_solicitudes_table(data.solicitudes_pendientes, verMas)}
			`);

			this.mount_charts($panel, metricas);
			this.bind_panel_handlers($panel);
		},



		render_ver_mas_btn(doctype, filters) {
			if (!doctype) return "";
			const filters_json = JSON.stringify(filters || []).replace(/'/g, "&#39;");
			return `
				<button type="button" class="btn btn-link btn-sm club-secretaria-ver-mas px-0"
					data-doctype="${frappe.utils.escape_html(doctype)}"
					data-filters="${filters_json.replace(/"/g, "&quot;")}">
					${__("Ver más")}
				</button>
			`;
		},

		normalize_filters(raw) {
			if (raw == null || raw === "") {
				return [];
			}
			if (Array.isArray(raw)) {
				return raw;
			}
			if (typeof raw === "string") {
				try {
					return JSON.parse(raw);
				} catch {
					return [];
				}
			}
			return [];
		},

		bind_panel_handlers($panel) {
			$panel.find(".club-secretaria-ver-mas").on("click", (e) => {
				const $btn = $(e.currentTarget);
				this.open_list($btn.attr("data-doctype"), $btn.attr("data-filters"));
			});

			$panel.find(".club-secretaria-nuevo-socio").on("click", () => {
				if (club_management_socio_alta_guiada?.open) {
					club_management_socio_alta_guiada.open();
				}
			});

			$panel.find(".club-secretaria-cobranza").on("click", () => {
				frappe.route_options = { saldo_deuda: [">", 0] };
				frappe.set_route("List", "Socio");
			});

			$panel.find(".club-secretaria-solicitud-row").on("click", (e) => {
				const name = $(e.currentTarget).data("name");
				if (name) {
					this.open_solicitud(name);
				}
			});

			$panel.find(".club-secretaria-solicitud-row").on("keydown", (e) => {
				if (e.key !== "Enter" && e.key !== " ") {
					return;
				}
				e.preventDefault();
				$(e.currentTarget).trigger("click");
			});
		},

		open_solicitud(name) {
			if (name) {
				frappe.set_route("Form", "Solicitud Asociacion", name);
			}
		},

		open_list(doctype, raw_filters) {
			if (!doctype) {
				return;
			}
			const filters = this.normalize_filters(raw_filters);
			if (filters.length) {
				frappe.route_options = filters.reduce((acc, filter) => {
					if (!Array.isArray(filter) || filter.length < 4) {
						return acc;
					}
					const field = filter[1];
					const value = [filter[2], filter[3]];
					if (acc[field]) {
						acc[field].push(value);
					} else {
						acc[field] = [value];
					}
					return acc;
				}, {});
			} else {
				frappe.route_options = {};
			}
			frappe.set_route("List", doctype);
		},



		refresh() {

			if (!this.is_secretaria_workspace()) {

				this.clear_mount();

				return;

			}



			const $parent = this.get_mount_parent();

			if (!$parent) {

				this.schedule_refresh();

				return;

			}



			const $panel = this.ensure_mount_point($parent);

			this.render_loading($panel);



			frappe.call({

				method: "club_management.members.api.secretaria_workspace.get_panel_lists",

				callback: (r) => {

					if (r.message) {

						this.render_lists($panel, r.message);

					}

				},

			});

		},

	};



	frappe.router.on("change", () => {

		club_management.secretaria_panel.schedule_refresh();

	});



	$(document).on("page-change app_ready", () => {

		club_management.secretaria_panel.schedule_refresh();

	});

})();

