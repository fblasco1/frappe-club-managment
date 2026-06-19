/* global frappe */

(function () {

	frappe.provide("club_management.secretaria_panel");



	const SECRETARIA_WORKSPACE_NAME = "Secretaría";

	const PANEL_ID = "club-secretaria-lists";



	club_management.secretaria_panel = {

		_refresh_timer: null,

		_cuotas_state: null,



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

			const container = ws.body.find(".editor-js-container");

			if (!container.length) return null;

			container.addClass("club-secretaria-workspace");

			return container;

		},



		clear_mount() {

			$(`#${PANEL_ID}`).remove();

			frappe.workspace?.body?.find(".editor-js-container")?.removeClass("club-secretaria-workspace");

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



		render_kpi_cards(metricas) {

			const socios = metricas.socios || {};

			const recaudacion = metricas.recaudacion || {};

			const verMas = metricas.ver_mas || {};

			const cuotas = recaudacion.cuotas_sociales || {};

			const aranceles = recaudacion.aranceles || {};

			const actividadRows = (aranceles.por_actividad || [])

				.map(

					(row) =>

						`<li><strong>${frappe.utils.escape_html(row.actividad)}</strong>: ${row.porcentaje}%</li>`

				)

				.join("");

			const actividadDetail =

				actividadRows.length > 0

					? `<details class="club-secretaria-aranceles-detail">

						<summary>${__("Detalle por actividad")}</summary>

						<ul>${actividadRows}</ul>

					</details>`

					: "";



			const morososDeudaLabel =
				socios.morosos_deuda_label ||
				frappe.format(socios.morosos_deuda || 0, { fieldtype: "Currency" });

			return `

				<div class="club-secretaria-kpi-grid">

					<div class="club-secretaria-kpi-card club-secretaria-kpi-card--morosos">

						<p class="club-secretaria-kpi-title">${__("Socios en mora")}</p>

						<div class="club-secretaria-kpi-value">${socios.morosos ?? 0}</div>

						<p class="club-secretaria-kpi-deuda">${frappe.utils.escape_html(morososDeudaLabel)}</p>

						<div class="club-secretaria-kpi-footer">

							${this.render_ver_mas_btn(

								verMas.socios_morosos_doctype,

								verMas.socios_morosos_filters

							)}

						</div>

					</div>

					<div class="club-secretaria-kpi-card">

						<p class="club-secretaria-kpi-title">${__("Cantidad de socios")}</p>

						<div class="club-secretaria-kpi-value">${socios.total ?? 0}</div>

						${this.render_delta(socios.delta_mes)}

						<div class="club-secretaria-kpi-footer">

							${this.render_ver_mas_btn(verMas.socios_total_doctype, verMas.socios_total_filters)}

						</div>

					</div>

					<div class="club-secretaria-kpi-card">

						<p class="club-secretaria-kpi-title">${__("Cuotas sociales recaudadas")}</p>

						<div class="club-secretaria-kpi-value club-secretaria-kpi-value--pct">${cuotas.porcentaje ?? 0}%</div>

						<span class="text-muted small">${__("Mes")} ${frappe.utils.escape_html(recaudacion.periodo || "")}</span>

					</div>

					<div class="club-secretaria-kpi-card">

						<p class="club-secretaria-kpi-title">${__("Aranceles recaudados")}</p>

						<div class="club-secretaria-kpi-value club-secretaria-kpi-value--pct">${aranceles.porcentaje ?? 0}%</div>

						<span class="text-muted small">${__("Mes")} ${frappe.utils.escape_html(recaudacion.periodo || "")}</span>

						${actividadDetail}

					</div>

				</div>

			`;

		},



		render_lists($panel, data) {

			const metricas = data.metricas || {};

			this._cuotas_state = data.cuotas_sociales || null;



			$panel.html(`

				<div class="club-secretaria-panel-actions">

					<button type="button" class="btn btn-primary club-secretaria-nuevo-socio">

						${__("Nuevo socio")}

					</button>

				</div>

				${this.render_kpi_cards(metricas)}

				<div class="col-12">

					${this.render_cuotas_html(this._cuotas_state)}

				</div>

			`);



			this.bind_panel_handlers($panel);

		},



		render_cuotas_html(cuotasData) {

			const cuotas = cuotasData?.cuotas || [];

			if (!cuotas.length) {

				return "";

			}

			const rows = cuotas

				.map(

					(row) => `

				<tr data-categoria="${frappe.utils.escape_html(row.categoria)}">

					<td>${frappe.utils.escape_html(row.categoria)}</td>

					<td>

						<input type="number" class="form-control form-control-sm club-cuota-monto"

							min="0" step="0.01" value="${frappe.utils.escape_html(String(row.monto || 0))}">

					</td>

					<td class="text-muted small">${frappe.utils.escape_html(row.item || cuotasData.item_cuota_social_default || "")}</td>

				</tr>`

				)

				.join("");

			return `

				<details class="club-secretaria-cuotas-collapse">

					<summary>

						<span class="club-secretaria-list-icon">💰</span>

						${__("Cuotas sociales por categoría")}

					</summary>

					<div class="table-responsive">

						<table class="table table-sm club-cuotas-table mb-2">

							<thead>

								<tr>

									<th>${__("Categoría")}</th>

									<th>${__("Monto mensual")}</th>

									<th>${__("Ítem ERPNext")}</th>

								</tr>

							</thead>

							<tbody>${rows}</tbody>

						</table>

					</div>

					<button type="button" class="btn btn-primary btn-sm club-secretaria-save-cuotas">

						${__("Guardar cuotas")}

					</button>

				</details>

			`;

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



			$panel.find(".club-secretaria-save-cuotas").on("click", () => this.save_cuotas($panel));

			$panel.find(".club-secretaria-nuevo-socio").on("click", () => {

				if (club_management_socio_alta_guiada?.open) {

					club_management_socio_alta_guiada.open();

				}

			});

		},



		save_cuotas($panel) {

			const rows = [];

			$panel.find(".club-cuotas-table tbody tr").each((_, tr) => {

				const $tr = $(tr);

				rows.push({

					categoria: $tr.data("categoria"),

					monto: parseFloat($tr.find(".club-cuota-monto").val()) || 0,

				});

			});

			frappe.call({

				method: "club_management.members.api.secretaria_workspace.save_cuotas_sociales",

				args: { rows },

				freeze: true,

				callback: (r) => {

					if (r.message) {

						frappe.show_alert({ message: __("Cuotas guardadas"), indicator: "green" });

						this._cuotas_state = r.message;

					}

				},

			});

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

