/* global frappe, club_management */

/**
 * Panel operativo de Tesorería (GF-6).
 *
 * Reemplaza el render nativo del workspace: botón de acción a la izquierda
 * (Crear Factura de Compra) y, debajo, listas de operaciones con plan de
 * cuenta y centro de costo. PAGOS PENDIENTES lista las facturas en Borrador
 * para que Tesorería las apruebe (Submit).
 */
(function () {
	frappe.provide("club_management.tesoreria_panel");

	const TESORERIA_WORKSPACE_NAME = "Tesorería";
	const PANEL_ID = "club-tesoreria-panel";

	club_management.tesoreria_panel = {
		_refresh_timer: null,

		schedule_refresh() {
			clearTimeout(this._refresh_timer);
			this._refresh_timer = setTimeout(() => this.refresh(), 150);
		},

		is_tesoreria_workspace() {
			// Chequeo por ruta (robusto: no depende de helpers que fallan en /desk).
			const route = frappe.get_route() || [];
			if (route[0] === "Workspaces") {
				return route[route.length - 1] === TESORERIA_WORKSPACE_NAME;
			}
			return frappe.workspace?._page?.name === TESORERIA_WORKSPACE_NAME;
		},

		get_mount_parent() {
			const ws = frappe.workspace;
			if (!ws?.body?.length) return null;
			const container = ws.body.find(".editor-js-container");
			if (!container.length) return null;
			$("body").addClass("club-tesoreria-active-workspace");
			ws.body.addClass("club-tesoreria-workspace-body");
			ws.body
				.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				.addClass("club-tesoreria-workspace-body");
			container.addClass("club-tesoreria-workspace");
			return container;
		},

		clear_mount() {
			$(`#${PANEL_ID}`).remove();
			$("body").removeClass("club-tesoreria-active-workspace");
			const ws = frappe.workspace;
			ws?.body?.find(".editor-js-container")?.removeClass("club-tesoreria-workspace");
			ws?.body?.removeClass("club-tesoreria-workspace-body");
			ws?.body
				?.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				?.removeClass("club-tesoreria-workspace-body");
		},

		ensure_mount_point($parent) {
			if ($(`#${PANEL_ID}`).length) {
				return $(`#${PANEL_ID}`);
			}
			const $panel = $(`<div id="${PANEL_ID}" class="club-tesoreria-panel"></div>`);
			$parent.prepend($panel);
			return $panel;
		},

		render_loading($panel) {
			$panel.html(`<div class="text-muted">${__("Cargando panel…")}</div>`);
		},

		render_actions() {
			return `
				<div class="club-tesoreria-actions">
					<button type="button" class="btn btn-primary club-tesoreria-nueva-fc">
						${__("Crear Factura de Compra")}
					</button>
				</div>
			`;
		},

		render_informes(data) {
			const inf = data.informes_contables;
			if (!inf || !inf.visible) return "";
			const botones = [
				[inf.ganancias_perdidas, __("Ganancias y pérdidas")],
				[inf.flujo_efectivo, __("Flujo de efectivo")],
				[inf.flujo_operativo, __("Proyección 5 días")],
			];
			const html = botones
				.filter(([report]) => report)
				.map(
					([report, label]) => `
					<button type="button" class="btn btn-default club-tesoreria-informe"
						data-report="${frappe.utils.escape_html(report)}">
						${frappe.utils.escape_html(label)}
					</button>`
				)
				.join("");
			return `<div class="club-tesoreria-actions club-tesoreria-informes">${html}</div>`;
		},

		render_liquidez(data) {
			const liq = data.liquidez;
			if (!liq) return "";
			const ventana = liq.ventana_dias || 5;
			const alcanza = liq.liquidez_alcanza
				? __("Alcanza obligaciones críticas")
				: __("No alcanza obligaciones críticas");
			const inf = data.informes_contables || {};
			const reportAttr =
				inf.visible && inf.flujo_operativo
					? ` data-report="${frappe.utils.escape_html(inf.flujo_operativo)}"`
					: "";
			return `
				<div class="club-tesoreria-kpis">
					<div class="club-tesoreria-kpi"${reportAttr}>
						<div class="club-tesoreria-kpi-label">${frappe.utils.escape_html(
							__("Liquidez a {0} días", [ventana])
						)}</div>
						<div class="club-tesoreria-kpi-value">${frappe.utils.escape_html(
							liq.liquidez_proyectada_label || ""
						)}</div>
						<div class="club-tesoreria-kpi-hint">${frappe.utils.escape_html(alcanza)}</div>
					</div>
					<div class="club-tesoreria-kpi">
						<div class="club-tesoreria-kpi-label">${frappe.utils.escape_html(
							__("Gastos proyectados (borrador)")
						)}</div>
						<div class="club-tesoreria-kpi-value">${frappe.utils.escape_html(
							liq.gastos_proyectados_pendientes_label || ""
						)}</div>
					</div>
				</div>
			`;
		},

		render_row(row) {
			const estado = row.estado
				? `<span class="club-tesoreria-badge">${frappe.utils.escape_html(row.estado)}</span>`
				: "";
			return `
				<tr class="club-tesoreria-row" data-doctype="${frappe.utils.escape_html(row.doctype)}" data-name="${frappe.utils.escape_html(row.name)}" role="button" tabindex="0">
					<td>${frappe.utils.escape_html(row.titulo || row.name)}</td>
					<td>${frappe.utils.escape_html(row.cuenta || "—")}</td>
					<td>${frappe.utils.escape_html(row.centro_costo || "—")}</td>
					<td class="text-nowrap">${frappe.utils.escape_html(row.fecha_label || "")}</td>
					<td class="text-right text-nowrap">${frappe.utils.escape_html(row.importe_label || "")}</td>
					<td>${estado}</td>
				</tr>
			`;
		},

		render_list_card(titulo, icon, rows) {
			const cuerpo = (rows || []).length
				? (rows || []).map((r) => this.render_row(r)).join("")
				: `<tr><td colspan="6" class="text-muted">${__("Sin registros.")}</td></tr>`;
			return `
				<div class="club-tesoreria-list-card">
					<div class="club-tesoreria-list-header">
						<span class="club-tesoreria-list-icon">${icon}</span>
						<h5 class="mb-0">${frappe.utils.escape_html(titulo)}</h5>
					</div>
					<div class="table-responsive">
						<table class="table table-sm mb-0 club-tesoreria-table">
							<thead>
								<tr>
									<th>${__("Detalle")}</th>
									<th>${__("Plan de cuenta")}</th>
									<th>${__("Centro de costo")}</th>
									<th>${__("Fecha")}</th>
									<th class="text-right">${__("Importe")}</th>
									<th>${__("Estado")}</th>
								</tr>
							</thead>
							<tbody>${cuerpo}</tbody>
						</table>
					</div>
				</div>
			`;
		},

		render_panel($panel, data) {
			$panel.html(`
				${this.render_actions()}
				${this.render_informes(data)}
				${this.render_liquidez(data)}
				${this.render_list_card(__("PAGOS PENDIENTES"), "📝", data.borradores_pendientes)}
				${this.render_list_card(__("PAGOS REALIZADOS"), "🧾", data.facturas_pagas)}
				${this.render_list_card(__("COBRANZA"), "💰", data.cobros_recibidos)}
			`);
			this.bind_handlers($panel);
		},

		bind_handlers($panel) {
			$panel.find(".club-tesoreria-nueva-fc").on("click", () => {
				frappe.new_doc("Purchase Invoice");
			});
			$panel.find(".club-tesoreria-informe, .club-tesoreria-kpi[data-report]").on("click", (e) => {
				const report = $(e.currentTarget).attr("data-report");
				if (report) {
					frappe.set_route("query-report", report);
				}
			});
			$panel.find(".club-tesoreria-row").on("click", (e) => {
				const $row = $(e.currentTarget);
				const doctype = $row.attr("data-doctype");
				const name = $row.attr("data-name");
				if (doctype && name) {
					frappe.set_route("Form", doctype, name);
				}
			});
			$panel.find(".club-tesoreria-row").on("keydown", (e) => {
				if (e.key !== "Enter" && e.key !== " ") return;
				e.preventDefault();
				$(e.currentTarget).trigger("click");
			});
		},

		refresh() {
			try {
				if (!this.is_tesoreria_workspace()) {
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
					method: "club_management.finance.api.tesoreria_panel.get_panel_data",
					callback: (r) => {
						if (r.message) {
							this.render_panel($panel, r.message);
						}
					},
				});
			} catch (e) {
				console.warn("tesoreria_panel:", e);
			}
		},
	};

	frappe.router.on("change", () => {
		club_management.tesoreria_panel.schedule_refresh();
	});

	$(document).on("page-change app_ready", () => {
		club_management.tesoreria_panel.schedule_refresh();
	});
})();
