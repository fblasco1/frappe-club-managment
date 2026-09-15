/* global frappe */

(function () {

	frappe.provide("club_management.secretaria_panel");



	const SECRETARIA_WORKSPACE_NAME = "Secretaría";

	const PANEL_ID = "club-secretaria-lists";



	club_management.secretaria_panel = {

		_refresh_timer: null,
		_selected_tendencia_month: null,
		_selected_tendencia_vista: "total",
		_$panel: null,



		get_tendencia_month_value() {
			if (this._selected_tendencia_month) {
				return this._selected_tendencia_month;
			}
			const now = frappe.datetime.str_to_obj(frappe.datetime.get_today());
			const month = String(now.getMonth() + 1).padStart(2, "0");
			return `${now.getFullYear()}-${month}`;
		},

		tendencia_reference_date() {
			return `${this.get_tendencia_month_value()}-01`;
		},

		get_tendencia_vista() {
			return this._selected_tendencia_vista || "total";
		},

		render_tendencia_month_input(selectedMonth) {
			return `
				<label class="club-secretaria-trend-month">
					<span class="text-muted small">${__("Mes")}</span>
					<input type="month" class="form-control form-control-sm club-secretaria-trend-month-input"
						value="${frappe.utils.escape_html(selectedMonth)}" />
				</label>
			`;
		},

		render_tendencia_vista_select(tendencia) {
			const vistas = tendencia?.vistas || [
				{ value: "total", label: __("Total") },
				{ value: "cuota", label: __("Cuotas sociales") },
				{ value: "arancel", label: __("Aranceles") },
				{ value: "cto_comp", label: __("CTO COMP") },
				{ value: "federativa", label: __("Federativas") },
				{ value: "otro", label: __("Otros conceptos") },
			];
			const selected = this.get_tendencia_vista();
			const options = vistas
				.map((opt) => {
					const value = frappe.utils.escape_html(opt.value);
					const label = frappe.utils.escape_html(opt.label);
					const sel = opt.value === selected ? " selected" : "";
					return `<option value="${value}"${sel}>${label}</option>`;
				})
				.join("");
			return `
				<label class="club-secretaria-cobrabilidad-filter club-secretaria-trend-vista">
					<span class="text-muted small">${__("Vista")}</span>
					<select class="form-control form-control-sm club-secretaria-trend-vista-select">
						${options}
					</select>
				</label>
			`;
		},

		schedule_refresh() {

			clearTimeout(this._refresh_timer);

			this._refresh_timer = setTimeout(() => this.refresh(), 150);

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
			const container = ws.body.find(".editor-js-container");
			if (!container.length) return null;
			$("body").addClass("club-secretaria-active-workspace");
			ws.body.addClass("club-secretaria-workspace-body");
			ws.body
				.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				.addClass("club-secretaria-workspace-body");
			ws.body.closest(".layout-main-section-wrapper").addClass("club-secretaria-workspace-body");
			container.addClass("club-secretaria-workspace");
			return container;
		},



		clear_mount() {
			$(`#${PANEL_ID}`).remove();
			$("body").removeClass("club-secretaria-active-workspace");
			const ws = frappe.workspace;
			ws?.body?.find(".editor-js-container")?.removeClass("club-secretaria-workspace");
			ws?.body?.removeClass("club-secretaria-workspace-body");
			ws?.body
				?.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
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

		get_cobrabilidad_slice(recaudacion, vista, detalle) {
			const empty = {
				emitido: 0,
				recaudado: 0,
				saldo_por_cobrar: 0,
				porcentaje: 0,
				recaudado_label: frappe.format(0, { fieldtype: "Currency" }),
				saldo_por_cobrar_label: frappe.format(0, { fieldtype: "Currency" }),
			};
			const rec = recaudacion || {};
			if (vista === "total") {
				return rec.total || empty;
			}
			if (vista === "cuota") {
				const base = rec.cuotas_sociales || empty;
				if (!detalle) {
					return base;
				}
				const row = (base.por_categoria || []).find((item) => item.categoria === detalle);
				return row || empty;
			}
			if (vista === "arancel") {
				const base = rec.aranceles || empty;
				if (!detalle) {
					return base;
				}
				const row = (base.por_actividad || []).find((item) => item.actividad === detalle);
				return row || empty;
			}
			const conceptBlock = rec[vista] || empty;
			if (!detalle) {
				return conceptBlock;
			}
			const conceptRow = (conceptBlock.por_concepto || []).find(
				(item) => item.concepto === detalle
			);
			return conceptRow || empty;
		},

		get_cobrabilidad_detalle_options(recaudacion, vista) {
			const rec = recaudacion || {};
			if (vista === "total") {
				return [];
			}
			if (vista === "cuota") {
				return (rec.cuotas_sociales?.por_categoria || []).map((row) => ({
					value: row.categoria,
					label: row.categoria,
				}));
			}
			if (vista === "arancel") {
				return (rec.aranceles?.por_actividad || []).map((row) => ({
					value: row.actividad,
					label: row.actividad,
				}));
			}
			const block = rec[vista];
			return (block?.por_concepto || []).map((row) => ({
				value: row.concepto,
				label: row.concepto,
			}));
		},

		get_cobrabilidad_report_link(cobranza, vista) {
			const byVista = cobranza?.report_by_vista || {};
			return (
				byVista[vista] ||
				cobranza?.rendicion_completa_report ||
				cobranza?.recaudado_cuotas_report ||
				null
			);
		},

		render_cobrabilidad_metrics(slice, cobranza, vista) {
			const data = slice || {};
			const cobrado =
				data.recaudado_label ||
				frappe.format(data.recaudado || 0, { fieldtype: "Currency" });
			const pendiente =
				data.saldo_por_cobrar_label ||
				frappe.format(data.saldo_por_cobrar ?? 0, { fieldtype: "Currency" });
			const reportLink = this.get_cobrabilidad_report_link(cobranza, vista);
			return `
				<div class="club-secretaria-kpi-value club-secretaria-kpi-value--pct">${data.porcentaje ?? 0}%</div>
				<div class="club-secretaria-kpi-breakdown">
					<div class="club-secretaria-kpi-breakdown-row">
						<span>${__("Total cobrado")}:</span>
						<strong>${frappe.utils.escape_html(cobrado)}</strong>
					</div>
					<div class="club-secretaria-kpi-breakdown-row">
						<span>${__("Saldo por cobrar")}:</span>
						<strong>${frappe.utils.escape_html(pendiente)}</strong>
					</div>
				</div>
				<div class="club-secretaria-kpi-footer">
					${this.render_report_link_btn(reportLink)}
				</div>
			`;
		},

		render_cobrabilidad_detalle_select(recaudacion, vista, detalle) {
			const options = this.get_cobrabilidad_detalle_options(recaudacion, vista);
			if (!options.length) {
				return "";
			}
			const rows = [
				`<option value="">${frappe.utils.escape_html(__("Todas"))}</option>`,
				...options.map(
					(opt) =>
						`<option value="${frappe.utils.escape_html(opt.value)}"${
							opt.value === detalle ? " selected" : ""
						}>${frappe.utils.escape_html(opt.label)}</option>`
				),
			].join("");
			return `
				<label class="club-secretaria-cobrabilidad-filter">
					<span class="text-muted small">${__("Detalle")}</span>
					<select class="form-control form-control-sm club-secretaria-cobrabilidad-detalle">
						${rows}
					</select>
				</label>
			`;
		},

		update_cobrabilidad_card($card) {
			if (!$card?.length) {
				return;
			}
			let recaudacion = {};
			try {
				recaudacion = JSON.parse($card.attr("data-recaudacion") || "{}");
			} catch {
				recaudacion = {};
			}
			const cobranza = JSON.parse($card.attr("data-cobranza") || "{}");
			const vista = $card.find(".club-secretaria-cobrabilidad-vista").val() || "total";
			const detalle = $card.find(".club-secretaria-cobrabilidad-detalle").val() || "";
			const slice = this.get_cobrabilidad_slice(recaudacion, vista, detalle);
			$card.find(".club-secretaria-cobrabilidad-metrics").html(
				this.render_cobrabilidad_metrics(slice, cobranza, vista)
			);
			const $detalleWrap = $card.find(".club-secretaria-cobrabilidad-detalle-wrap");
			const detalleHtml = this.render_cobrabilidad_detalle_select(recaudacion, vista, detalle);
			if (detalleHtml) {
				$detalleWrap.html(detalleHtml).show();
			} else {
				$detalleWrap.empty().hide();
			}
		},

		render_cobrabilidad_card(metricas) {
			const recaudacion = metricas.recaudacion || {};
			const verMas = metricas.ver_mas || {};
			const cobranza = verMas.cobranza || {};
			const periodo = cobranza.periodo || recaudacion.periodo || "";
			const vistas = recaudacion.cobrabilidad_vistas || [
				{ value: "total", label: __("Total") },
				{ value: "cuota", label: __("Cuotas sociales") },
				{ value: "arancel", label: __("Aranceles") },
			];
			const vistaOptions = vistas
				.map(
					(opt) =>
						`<option value="${frappe.utils.escape_html(opt.value)}">${frappe.utils.escape_html(
							opt.label
						)}</option>`
				)
				.join("");
			const slice = this.get_cobrabilidad_slice(recaudacion, "total", "");
			const recaudacionJson = JSON.stringify(recaudacion).replace(/'/g, "&#39;");
			const cobranzaJson = JSON.stringify(cobranza).replace(/'/g, "&#39;");

			return `
				<div class="club-secretaria-kpi-card club-secretaria-kpi-card--cobrabilidad"
					data-recaudacion='${recaudacionJson.replace(/"/g, "&quot;")}'
					data-cobranza='${cobranzaJson.replace(/"/g, "&quot;")}'>
					<div class="club-secretaria-cobrabilidad-header">
						<div>
							<p class="club-secretaria-kpi-title">${__("Tasa de cobrabilidad del mes")}</p>
							<span class="text-muted small">${__("Mes")} ${frappe.utils.escape_html(periodo)}</span>
						</div>
						<label class="club-secretaria-cobrabilidad-filter">
							<span class="text-muted small">${__("Vista")}</span>
							<select class="form-control form-control-sm club-secretaria-cobrabilidad-vista">
								${vistaOptions}
							</select>
						</label>
					</div>
					<div class="club-secretaria-cobrabilidad-detalle-wrap" style="display:none"></div>
					<div class="club-secretaria-cobrabilidad-metrics">
						${this.render_cobrabilidad_metrics(slice, cobranza, "total")}
					</div>
				</div>
			`;
		},

		render_report_link_btn(link) {
			if (!link?.report) {
				return "";
			}
			const filters_json = JSON.stringify(link.filters || {}).replace(/'/g, "&#39;");
			return `
				<button type="button" class="btn btn-link btn-sm club-secretaria-ver-report px-0"
					data-report="${frappe.utils.escape_html(link.report)}"
					data-filters="${filters_json.replace(/"/g, "&quot;")}">
					${__("Ver informe")}
				</button>
			`;
		},

		render_kpi_cards(metricas) {
			const socios = metricas.socios || {};
			const morososDeudaLabel =
				socios.morosos_deuda_label ||
				frappe.format(socios.morosos_deuda || 0, { fieldtype: "Currency" });
			const verMas = metricas.ver_mas || {};

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
					${this.render_cobrabilidad_card(metricas)}
					<div class="club-secretaria-kpi-card">
						<p class="club-secretaria-kpi-title">${__("Altas vs bajas (mes)")}</p>
						<div class="club-secretaria-kpi-value club-secretaria-kpi-value--ratio">
							${this.render_altas_bajas(socios.altas_bajas)}
						</div>
					</div>
					<div class="club-secretaria-kpi-card club-secretaria-kpi-card--morosos">
						<p class="club-secretaria-kpi-title">${__("Socios en mora")}</p>
						<div class="club-secretaria-kpi-value">${socios.morosos ?? 0}</div>
						<p class="club-secretaria-kpi-deuda">${frappe.utils.escape_html(morososDeudaLabel)}</p>
						<div class="club-secretaria-kpi-footer">
							${this.render_ver_mas_btn(verMas.socios_morosos_doctype, verMas.socios_morosos_filters)}
						</div>
					</div>
				</div>
			`;
		},

		has_segmentos_chart(segmentos) {
			const s = segmentos || {};
			return (s.total || 0) > 0;
		},

		has_medios_chart(medios) {
			return Boolean(medios?.disponible);
		},

		has_medios_montos(medios) {
			const m = medios || {};
			return Boolean(m.efectivo || m.tarjeta || m.transferencia || m.otro);
		},

		render_charts(metricas) {
			const socios = metricas.socios || {};
			const tendencia = metricas.tendencia_recaudacion || {};
			const medios = metricas.medios_pago || {};
			const showTrend = tendencia.disponible && (tendencia.dias || []).length;
			const showSegmentos = this.has_segmentos_chart(socios.segmentos);
			const showMedios = this.has_medios_chart(medios);
			if (!showTrend && !showSegmentos && !showMedios) {
				return "";
			}
			const trendHtml = showTrend
				? `<div class="club-secretaria-charts-row club-secretaria-charts-row--trend">
					<div class="club-secretaria-chart-card club-secretaria-chart-card--wide">
						<div class="club-secretaria-chart-header">
							<div class="club-secretaria-chart-header-title">
								<h6>${__("Tendencia de recaudación")}</h6>
							</div>
							<div class="club-secretaria-chart-header-filters">
								${this.render_tendencia_vista_select(tendencia)}
								${this.render_tendencia_month_input(this.get_tendencia_month_value())}
							</div>
						</div>
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

		mount_trend_chart($container, tendencia) {
			if (!$container?.length) {
				return;
			}
			$container.empty();
			const data = tendencia || {};
			if (!data.disponible || !(data.dias || []).length) {
				$container.html(
					`<p class="text-muted mb-0">${__("Sin datos de recaudación para este mes.")}</p>`
				);
				this._chart_trend = null;
				return;
			}
			this._chart_trend = new frappe.Chart($container[0], {
				type: "line",
				height: 220,
				colors: ["#e74c3c", "#29cd42"],
				data: {
					labels: data.dias.map((row) => row.label),
					datasets: [
						{ name: __("Deuda del mes"), values: data.dias.map((r) => r.deuda) },
						{ name: __("Recaudado"), values: data.dias.map((r) => r.recaudado) },
					],
				},
				truncateLegends: 1,
				axisOptions: { shortenYAxisNumbers: 1 },
			});
		},

		mount_medios_chart($container, medios) {
			if (!$container?.length || !this.has_medios_chart(medios)) {
				return;
			}
			$container.empty();
			if (!this.has_medios_montos(medios)) {
				$container.html(
					`<p class="text-muted mb-0">${__("Sin cobros del mes")}</p>`
				);
				this._chart_medios = null;
				return;
			}
			this._chart_medios = new frappe.Chart($container[0], {
				type: "donut",
				height: 260,
				colors: ["#29cd42", "#5e64ff", "#f39c12", "#95a5a6"],
				data: {
					labels: [
						__("Efectivo"),
						__("Tarjeta"),
						__("Transferencia"),
						__("Otro"),
					],
					datasets: [
						{
							values: [
								medios.efectivo || 0,
								medios.tarjeta || 0,
								medios.transferencia || 0,
								medios.otro || 0,
							],
						},
					],
				},
			});
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
							__("Activo"),
							__("Menor"),
							__("Adherente"),
							__("Jubilado"),
							__("Vitalicio"),
						],
						datasets: [
							{
								name: __("Socios"),
								values: [
									segmentos.Activo || 0,
									segmentos.Menor || 0,
									segmentos.Adherente || 0,
									segmentos.Jubilado || 0,
									segmentos.Vitalicio || 0,
								],
							},
						],
					},
					barOptions: { spaceRatio: 0.45 },
					axisOptions: { shortenYAxisNumbers: 1 },
				});
			}
			this.mount_trend_chart($panel.find(".club-secretaria-chart-trend"), tendencia);
			this.mount_medios_chart($panel.find(".club-secretaria-chart-medios"), medios);
		},

		refresh_tendencia_chart($panel) {
			const $panelEl = $panel || this._$panel;
			if (!$panelEl?.length) {
				return;
			}
			const $trend = $panelEl.find(".club-secretaria-chart-trend");
			if (!$trend.length) {
				return;
			}
			$trend.html(`<div class="text-muted small py-3">${__("Cargando gráfico…")}</div>`);
			frappe.call({
				method: "club_management.members.api.secretaria_workspace.get_tendencia_recaudacion",
				args: {
					tendencia_reference_date: this.tendencia_reference_date(),
					vista: this.get_tendencia_vista(),
				},
				callback: (r) => {
					this.mount_trend_chart($trend, r.message || {});
				},
			});
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

		render_recordatorio_sueldos(recordatorio) {
			const data = recordatorio || {};
			if (!data.mostrar) {
				return "";
			}
			const pendientes = data.conceptos_pendientes || [];
			const lista =
				pendientes.length > 0
					? `<ul class="club-secretaria-sueldos-list mb-2">
					${pendientes
						.map(
							(row) => `
						<li>
							<strong>${frappe.utils.escape_html(row.label)}</strong>
							<span class="text-muted small d-block">
								${__("Proveedor")}: ${frappe.utils.escape_html(row.supplier_label || row.supplier || "")}
								· ${__("Ítem")}: ${frappe.utils.escape_html(row.item_code || "")}
							</span>
						</li>`
						)
						.join("")}
				</ul>`
					: `<p class="mb-2 text-success">${__("Todos los conceptos de provisión ya tienen factura este mes.")}</p>`;

			const btn =
				pendientes.length > 0
					? `<button type="button" class="btn btn-sm btn-primary club-secretaria-nueva-pi">
						${__("Nueva factura de compra")}
					</button>`
					: "";

			return `
				<div class="club-secretaria-sueldos-banner alert alert-warning" role="status">
					<h6 class="alert-heading mb-2">${__("Provisión de sueldos — último día hábil")}</h6>
					<p class="mb-2">${frappe.utils.escape_html(data.mensaje || "")}</p>
					${lista}
					${btn}
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
					<button type="button" class="btn btn-secondary club-secretaria-nuevo-gasto">
						${__("Registrar Nuevo Gasto / Comprobante")}
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
			this._$panel = $panel;

			$panel.html(`
				${this.render_recordatorio_sueldos(data.recordatorio_sueldos)}
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
			$panel.find(".club-secretaria-trend-month-input").on("change", (e) => {
				const value = e.currentTarget.value;
				if (value) {
					this._selected_tendencia_month = value;
					this.refresh_tendencia_chart($panel);
				}
			});

			$panel.find(".club-secretaria-trend-vista-select").on("change", (e) => {
				this._selected_tendencia_vista = e.currentTarget.value || "total";
				this.refresh_tendencia_chart($panel);
			});

			$panel.find(".club-secretaria-ver-mas").on("click", (e) => {
				const $btn = $(e.currentTarget);
				this.open_list($btn.attr("data-doctype"), $btn.attr("data-filters"));
			});

			$panel.find(".club-secretaria-ver-report").on("click", (e) => {
				const $btn = $(e.currentTarget);
				this.open_report($btn.attr("data-report"), $btn.attr("data-filters"));
			});

			$panel.on("change", ".club-secretaria-cobrabilidad-vista", (e) => {
				const $card = $(e.currentTarget).closest(".club-secretaria-kpi-card--cobrabilidad");
				$card.find(".club-secretaria-cobrabilidad-detalle").val("");
				this.update_cobrabilidad_card($card);
			});

			$panel.on("change", ".club-secretaria-cobrabilidad-detalle", (e) => {
				const $card = $(e.currentTarget).closest(".club-secretaria-kpi-card--cobrabilidad");
				this.update_cobrabilidad_card($card);
			});

			$panel.find(".club-secretaria-kpi-card--cobrabilidad").each((_, el) => {
				this.update_cobrabilidad_card($(el));
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

			$panel.find(".club-secretaria-nueva-pi").on("click", () => {
				frappe.set_route("Form", "Purchase Invoice", "new");
			});

			$panel.find(".club-secretaria-nuevo-gasto").on("click", () => {
				frappe.new_doc("Purchase Invoice");
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

		parse_report_filters(raw) {
			if (raw == null || raw === "") {
				return {};
			}
			if (typeof raw === "object" && !Array.isArray(raw)) {
				return raw;
			}
			if (typeof raw === "string") {
				try {
					const parsed = JSON.parse(raw);
					return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
				} catch {
					return {};
				}
			}
			return {};
		},

		open_report(reportName, rawFilters) {
			if (!reportName) {
				return;
			}
			frappe.route_options = this.parse_report_filters(rawFilters);
			frappe.set_route("query-report", reportName);
		},



		refresh() {

			if (!this.is_secretaria_workspace()) {

				this.clear_mount();

				return;

			}

			club_management.actividades_panel?.clear_mount?.();
			club_management.secretaria_sidebar?.refresh?.();



			const $parent = this.get_mount_parent();

			if (!$parent) {

				this.schedule_refresh();

				return;

			}



			const $panel = this.ensure_mount_point($parent);

			this.render_loading($panel);



			frappe.call({

				method: "club_management.members.api.secretaria_workspace.get_panel_lists",
				args: {
					tendencia_reference_date: this.tendencia_reference_date(),
					tendencia_vista: this.get_tendencia_vista(),
				},

				callback: (r) => {

					if (r.message) {

						this.render_lists($panel, r.message);

					}

				},

			});

		},

	};



	frappe.router.on("change", () => {
		if (!club_management.secretaria_panel.is_secretaria_workspace()) {
			club_management.secretaria_panel.clear_mount();
		}
		club_management.secretaria_panel.schedule_refresh();
	});



	$(document).on("page-change app_ready", () => {

		club_management.secretaria_panel.schedule_refresh();

	});

})();

