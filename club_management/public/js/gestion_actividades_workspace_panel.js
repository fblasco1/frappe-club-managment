/* global frappe */
(function () {
	frappe.provide("club_management.actividades_panel");

	const ACTIVIDADES_WORKSPACE_NAME = "Gestión de Actividades";
	const PANEL_ID = "club-actividades-catalog";
	const DASHBOARD_ID = "club-actividades-dashboard";

	club_management.actividades_panel = {
		_refresh_timer: null,
		_catalog: null,
		_dashboard: null,
		_dashboard_actividad: "",
		_chart_ocupacion: null,
		_ocupacion_raw: null,
		_ocupacion_actividades_ocultas: null,
		_selected_actividad: null,
		_grupo_expandido: null,
		_filter: "",
		_scroll_top: 0,
		_focus_selector: null,

		_storage_key(name) {
			return `club_actividades_panel_${name}`;
		},

		_ocupacion_storage_key() {
			return this._storage_key("ocupacion_ocultas");
		},

		load_ocupacion_ocultas() {
			if (this._ocupacion_actividades_ocultas) {
				return this._ocupacion_actividades_ocultas;
			}
			try {
				const raw = sessionStorage.getItem(this._ocupacion_storage_key());
				this._ocupacion_actividades_ocultas = raw ? new Set(JSON.parse(raw)) : new Set();
			} catch (_e) {
				this._ocupacion_actividades_ocultas = new Set();
			}
			return this._ocupacion_actividades_ocultas;
		},

		persist_ocupacion_ocultas() {
			try {
				const ocultas = this.load_ocupacion_ocultas();
				sessionStorage.setItem(this._ocupacion_storage_key(), JSON.stringify([...ocultas]));
			} catch (_e) {
				/* ignore */
			}
		},

		prune_ocupacion_ocultas(ocupacion) {
			const ocultas = this.load_ocupacion_ocultas();
			const valid = new Set(ocupacion?.labels || []);
			let changed = false;
			for (const act of [...ocultas]) {
				if (!valid.has(act)) {
					ocultas.delete(act);
					changed = true;
				}
			}
			if (changed) {
				this.persist_ocupacion_ocultas();
			}
		},

		filter_ocupacion_payload(ocupacion) {
			if (!ocupacion?.disponible) {
				return ocupacion;
			}
			this.prune_ocupacion_ocultas(ocupacion);
			const ocultas = this.load_ocupacion_ocultas();
			const indices = (ocupacion.labels || [])
				.map((label, index) => (ocultas.has(label) ? -1 : index))
				.filter((index) => index >= 0);
			if (indices.length === (ocupacion.labels || []).length) {
				return ocupacion;
			}
			return {
				...ocupacion,
				labels: indices.map((index) => ocupacion.labels[index]),
				label_titulos: indices.map(
					(index) => (ocupacion.label_titulos || ocupacion.labels)[index]
				),
			};
		},

		render_ocupacion_filtros(ocupacion) {
			const actividades = ocupacion?.actividades_filtro || [];
			if (!actividades.length) {
				return "";
			}
			const ocultas = this.load_ocupacion_ocultas();
			const chips = actividades
				.map((act) => {
					const checked = !ocultas.has(act.name);
					return `
					<label class="club-actividades-ocupacion-filter">
						<input type="checkbox" class="club-actividades-ocupacion-filter-item" value="${frappe.utils.escape_html(act.name)}" ${checked ? "checked" : ""}>
						<span>${frappe.utils.escape_html(act.titulo || act.name)}</span>
					</label>`;
				})
				.join("");
			return `
				<div class="club-actividades-ocupacion-filters">
					<div class="club-actividades-ocupacion-filters-head">
						<span class="small text-muted">${__("Mostrar actividades")}</span>
						<div class="club-actividades-ocupacion-filters-actions">
							<button type="button" class="btn btn-link btn-sm p-0 club-actividades-ocupacion-all">${__("Todas")}</button>
							<span class="text-muted">·</span>
							<button type="button" class="btn btn-link btn-sm p-0 club-actividades-ocupacion-none">${__("Ninguna")}</button>
						</div>
					</div>
					<div class="club-actividades-ocupacion-filters-list">${chips}</div>
				</div>`;
		},

		destroy_ocupacion_chart() {
			const parent = this._chart_ocupacion?.parent;
			if (parent) {
				parent.innerHTML = "";
			}
			if (parent) {
				$(parent).closest(".club-actividades-chart-ocupacion").find(".club-actividades-ocupacion-tip").remove();
			}
			this._chart_ocupacion = null;
		},

		setup_ocupacion_tooltip(chart, $wrap, ocupacion) {
			const composicion = ocupacion.composicion || {};
			const labels = ocupacion.labels || [];
			const titulos = ocupacion.label_titulos || labels;
			const $canvas = $wrap.find(".club-actividades-chart-ocupacion-canvas");
			let $tip = $wrap.find(".club-actividades-ocupacion-tip");
			if (!$tip.length) {
				$tip = $('<div class="club-actividades-ocupacion-tip"></div>').appendTo($wrap);
			}
			const hideTip = () => {
				$tip.removeClass("is-visible");
			};
			const segmentos_from_chart = (listValues) =>
				(listValues || [])
					.filter((row) => (row.value || 0) > 0)
					.map((row) => ({
						grupo_label: row.title,
						inscriptos: row.value,
						color: row.color || "#636e72",
					}));
			chart.tip.setValues = (x, y, title, listValues, index) => {
				const actividad = labels[index];
				const segmentos = composicion[actividad]?.length
					? composicion[actividad]
					: segmentos_from_chart(listValues);
				if (!segmentos.length) {
					hideTip();
					return;
				}
				const total = segmentos.reduce((sum, row) => sum + (row.inscriptos || 0), 0);
				const rows = segmentos
					.map(
						(row) => `
					<li>
						<span class="club-actividades-ocupacion-tip-dot" style="background:${row.color};"></span>
						<span class="club-actividades-ocupacion-tip-label">${frappe.utils.escape_html(row.grupo_label || row.grupo || "")}</span>
						<strong class="club-actividades-ocupacion-tip-value">${row.inscriptos ?? 0}</strong>
					</li>`
					)
					.join("");
				$tip.html(`
					<div class="club-actividades-ocupacion-tip-title">${frappe.utils.escape_html(titulos[index] || title.name || "")}</div>
					<div class="club-actividades-ocupacion-tip-total">${total} ${__("inscriptos")}</div>
					<ul class="club-actividades-ocupacion-tip-list">${rows}</ul>
				`);
				$tip.addClass("is-visible");
				const canvasOffset = $canvas.position();
				const wrapWidth = $wrap.innerWidth();
				const tipWidth = $tip.outerWidth();
				let left = canvasOffset.left + x - tipWidth / 2;
				left = Math.max(8, Math.min(left, wrapWidth - tipWidth - 8));
				const top = Math.max(8, canvasOffset.top + y - $tip.outerHeight() - 12);
				$tip.css({ left, top });
			};
			chart.tip.showTip = () => {};
			chart.tip.hideTip = hideTip;
			$wrap.off("mouseleave.clubOcupacionTip").on("mouseleave.clubOcupacionTip", hideTip);
		},

		mount_ocupacion_chart($panel, ocupacion) {
			this.destroy_ocupacion_chart();
			const filtered = this.filter_ocupacion_payload(ocupacion);
			const $ocup = $panel.find(".club-actividades-chart-ocupacion");
			if (!$ocup.length || !filtered?.disponible || !filtered.labels?.length) {
				if ($ocup.length) {
					$ocup.empty();
				}
				return;
			}
			$ocup.html('<div class="club-actividades-chart-ocupacion-canvas"></div>');
			const $canvas = $ocup.find(".club-actividades-chart-ocupacion-canvas");
			const visibleIndices = filtered.labels.map((label) => (ocupacion.labels || []).indexOf(label));
			const colors = filtered.colors || (ocupacion.datasets || []).map((ds) => ds.color).filter(Boolean);
			this._chart_ocupacion = new frappe.Chart($canvas[0], {
				type: "bar",
				height: 260,
				colors,
				showLegend: 0,
				data: {
					labels: filtered.label_titulos || filtered.labels,
					datasets: (ocupacion.datasets || []).map((ds) => ({
						name: ds.name,
						values: visibleIndices.map((index) => (ds.values || [])[index] || 0),
					})),
				},
				barOptions: { stacked: 1, spaceRatio: 0.45 },
				axisOptions: { shortenYAxisNumbers: 1 },
			});
			this.setup_ocupacion_tooltip(this._chart_ocupacion, $ocup, filtered);
		},

		refresh_ocupacion_chart($panel) {
			if (!this._ocupacion_raw) {
				return;
			}
			this.mount_ocupacion_chart($panel, this._ocupacion_raw);
		},

		bind_ocupacion_filtros($panel) {
			const sync_from_inputs = () => {
				const ocultas = new Set();
				$panel.find(".club-actividades-ocupacion-filter-item").each((_i, el) => {
					if (!el.checked) {
						ocultas.add(el.value);
					}
				});
				this._ocupacion_actividades_ocultas = ocultas;
				this.persist_ocupacion_ocultas();
				this.refresh_ocupacion_chart($panel);
			};
			$panel.off(".clubOcupacionFilter");
			$panel.on("change.clubOcupacionFilter", ".club-actividades-ocupacion-filter-item", sync_from_inputs);
			$panel.on("click.clubOcupacionFilter", ".club-actividades-ocupacion-all", (e) => {
				e.preventDefault();
				this._ocupacion_actividades_ocultas = new Set();
				this.persist_ocupacion_ocultas();
				$panel.find(".club-actividades-ocupacion-filter-item").prop("checked", true);
				this.refresh_ocupacion_chart($panel);
			});
			$panel.on("click.clubOcupacionFilter", ".club-actividades-ocupacion-none", (e) => {
				e.preventDefault();
				const all = (this._ocupacion_raw?.labels || []).slice();
				this._ocupacion_actividades_ocultas = new Set(all);
				this.persist_ocupacion_ocultas();
				$panel.find(".club-actividades-ocupacion-filter-item").prop("checked", false);
				this.refresh_ocupacion_chart($panel);
			});
		},

		load_persisted_state() {
			try {
				this._selected_actividad = sessionStorage.getItem(this._storage_key("actividad"));
				this._grupo_expandido = sessionStorage.getItem(this._storage_key("grupo"));
			} catch (_e) {
				this._selected_actividad = null;
				this._grupo_expandido = null;
			}
		},

		persist_state() {
			try {
				if (this._selected_actividad) {
					sessionStorage.setItem(this._storage_key("actividad"), this._selected_actividad);
				} else {
					sessionStorage.removeItem(this._storage_key("actividad"));
				}
				if (this._grupo_expandido) {
					sessionStorage.setItem(this._storage_key("grupo"), this._grupo_expandido);
				} else {
					sessionStorage.removeItem(this._storage_key("grupo"));
				}
			} catch (_e) {
				/* ignore */
			}
		},

		filtered_catalog() {
			const q = (this._filter || "").trim().toLowerCase();
			if (!q) {
				return this._catalog || [];
			}
			return (this._catalog || []).filter((act) => {
				const haystack = [
					act.titulo,
					act.name,
					...(act.grupos || []).flatMap((g) => [
						g.titulo,
						...(g.equipos || []).map((e) => e.titulo),
					]),
				]
					.join(" ")
					.toLowerCase();
				return haystack.includes(q);
			});
		},

		ensure_selected_actividad(catalog) {
			if (!catalog.length) {
				this._selected_actividad = null;
				return;
			}
			if (
				this._selected_actividad &&
				catalog.some((act) => act.name === this._selected_actividad)
			) {
				return;
			}
			this._selected_actividad = null;
		},

		get_selected_actividad() {
			return (this._catalog || []).find((act) => act.name === this._selected_actividad);
		},

		schedule_refresh() {
			clearTimeout(this._refresh_timer);
			this._refresh_timer = setTimeout(() => this.refresh(), 150);
		},

		is_actividades_workspace() {
			const nav = club_management.club_desk_navigation;
			if (nav?.get_club_workspace_name) {
				return nav.get_club_workspace_name() === ACTIVIDADES_WORKSPACE_NAME;
			}
			const page = frappe.workspace?._page;
			return page?.name === ACTIVIDADES_WORKSPACE_NAME;
		},

		is_catalog_page() {
			return club_management.club_desk_navigation?.get_active_page?.() === "catalogo-actividades";
		},

		get_mount_parent() {
			const ws = frappe.workspace;
			if (!ws?.body?.length) {
				return null;
			}
			const container = ws.body.find(".editor-js-container");
			if (!container.length) {
				return null;
			}
			$("body").addClass("club-actividades-active-workspace");
			ws.body.addClass("club-actividades-workspace-body");
			ws.body
				.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				.addClass("club-actividades-workspace-body");
			ws.body.closest(".layout-main-section-wrapper").addClass("club-actividades-workspace-body");
			container.addClass("club-actividades-workspace");
			return container;
		},

		clear_mount() {
			$(`#${DASHBOARD_ID}`).remove();
			$("body").removeClass("club-actividades-active-workspace club-actividades-catalog-active");
			const ws = frappe.workspace;
			ws?.body?.find(".editor-js-container")?.removeClass("club-actividades-workspace");
			ws?.body?.removeClass("club-actividades-workspace-body");
			ws?.body
				?.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				?.removeClass("club-actividades-workspace-body");
		},

		ensure_dashboard_mount($parent) {
			if ($(`#${DASHBOARD_ID}`).length) {
				return $(`#${DASHBOARD_ID}`);
			}
			const $dash = $(`<div id="${DASHBOARD_ID}" class="club-actividades-dashboard"></div>`);
			const $editor = $parent.find("#editorjs");
			if ($editor.length) {
				$editor.before($dash);
			} else {
				$parent.prepend($dash);
			}
			return $dash;
		},

		init_catalog_page(page) {
			this._catalog_page = page;
			$("body").addClass("club-actividades-catalog-active");
			page.main.addClass("club-actividades-catalog-page");
			page.main
				.parents(
					".layout-main-section-wrapper, .layout-main-section, .page-body, .container, .layout-main, main"
				)
				.addClass("club-actividades-catalog-page");
			if (!page.main.find(`#${PANEL_ID}`).length) {
				page.main.html(`<div id="${PANEL_ID}" class="club-actividades-catalog"></div>`);
			}
			this.refresh_catalog_page();
		},

		refresh_catalog_page() {
			const $panel = this._catalog_page?.main?.find(`#${PANEL_ID}`);
			if (!$panel?.length) {
				return;
			}
			this.load_catalog($panel);
		},

		load_catalog($panel) {
			this.render_loading($panel);
			frappe.call({
				method: "club_management.activities.api.gestion_actividades_workspace.get_catalog",
				callback: (r) => {
					if (r.message) {
						this.render_catalog($panel, r.message);
					}
				},
				error: () => {
					$panel.html(
						`<p class="text-danger">${__("No se pudo cargar el catálogo de actividades.")}</p>`
					);
				},
			});
		},

		render_loading($panel) {
			$panel.html(`<div class="text-muted">${__("Cargando catálogo…")}</div>`);
		},

		render_dashboard_loading($panel) {
			$panel.html(`<div class="text-muted">${__("Cargando panel de actividades…")}</div>`);
		},

		render_semaforo_class(semaforo) {
			if (semaforo === "amarillo") return "is-semaforo-amarillo";
			if (semaforo === "rojo") return "is-semaforo-rojo";
			return "";
		},

		render_ver_mas_btn(doctype, filters) {
			if (!doctype) return "";
			const filters_json = JSON.stringify(filters || []).replace(/'/g, "&#39;");
			return `
				<button type="button" class="btn btn-link btn-sm club-actividades-ver-mas px-0"
					data-doctype="${frappe.utils.escape_html(doctype)}"
					data-filters="${filters_json.replace(/"/g, "&quot;")}">
					${__("Ver más")}
				</button>
			`;
		},

		normalize_filters(raw) {
			if (raw == null || raw === "") return [];
			if (Array.isArray(raw)) return raw;
			if (typeof raw === "string") {
				try {
					return JSON.parse(raw);
				} catch {
					return [];
				}
			}
			return [];
		},

		open_list(doctype, raw_filters) {
			if (!doctype) return;
			const filters = this.normalize_filters(raw_filters);
			if (filters.length) {
				frappe.route_options = filters.reduce((acc, filter) => {
					if (!Array.isArray(filter) || filter.length < 4) return acc;
					const field = filter[1];
					const value = [filter[2], filter[3]];
					if (acc[field]) acc[field].push(value);
					else acc[field] = [value];
					return acc;
				}, {});
			} else {
				frappe.route_options = {};
			}
			frappe.set_route("List", doctype);
		},

		render_dashboard_quick_actions() {
			return `
				<div class="club-actividades-quick-actions">
					<button type="button" class="btn btn-primary club-actividades-inscribir">
						${__("+ Inscribir socio a actividad")}
					</button>
					<button type="button" class="btn btn-secondary club-actividades-cupos">
						${__("Modificar cupos / horarios")}
					</button>
				</div>
			`;
		},

		render_dashboard_kpis(data) {
			const kpis = data.kpis || {};
			const verMas = data.ver_mas || {};
			const crecimiento = kpis.crecimiento || {};
			const masSocios = kpis.mas_socios || {};
			return `
				<div class="club-actividades-kpi-grid">
					<div class="club-actividades-kpi-card">
						<p class="club-actividades-kpi-title">${__("Inscripciones activas")}</p>
						<div class="club-actividades-kpi-value">${kpis.inscripciones_activas ?? 0}</div>
						<div class="club-actividades-kpi-footer">
							${this.render_ver_mas_btn(verMas.inscripciones_doctype, verMas.inscripciones_filters)}
						</div>
					</div>
					<div class="club-actividades-kpi-card">
						<p class="club-actividades-kpi-title">${__("Actividad con mayor crecimiento del mes")}</p>
						<div class="club-actividades-kpi-value">${frappe.utils.escape_html(crecimiento.actividad || "—")}</div>
						<span class="text-muted small">+${crecimiento.altas_mes ?? 0} (${crecimiento.delta_mes_anterior ?? 0} ${__("vs mes anterior")})</span>
					</div>
					<div class="club-actividades-kpi-card">
						<p class="club-actividades-kpi-title">${__("Actividad con más socios inscriptos")}</p>
						<div class="club-actividades-kpi-value">${frappe.utils.escape_html(masSocios.actividad || "—")}</div>
						<span class="text-muted small">${masSocios.socios ?? 0} ${__("socios")}</span>
						<div class="club-actividades-kpi-footer">
							${this.render_ver_mas_btn(verMas.mas_socios_doctype, verMas.mas_socios_filters)}
						</div>
					</div>
				</div>
			`;
		},

		render_dashboard_charts_html(data) {
			const ocupacion = data.ocupacion_por_deporte || {};
			const infra = data.infraestructura || {};
			const lista = data.lista_espera || {};
			const ocupacionHtml = ocupacion.disponible
				? `<div class="club-actividades-chart-card club-actividades-chart-card--wide">
					<h6>${__("Inscripciones por deporte / actividad")}</h6>
					${this.render_ocupacion_filtros(ocupacion)}
					<div class="club-actividades-chart-ocupacion"></div>
				</div>`
				: "";
			const listaRows = (lista.filas || [])
				.map(
					(row) => `
				<tr>
					<td>${frappe.utils.escape_html(row.actividad || "")}</td>
					<td>${frappe.utils.escape_html(row.grupo_actividad || row.equipo_actividad || "—")}</td>
					<td>${row.cantidad ?? 0}</td>
					<td>${frappe.datetime.str_to_user(row.fecha_mas_antigua) || ""}</td>
				</tr>`
				)
				.join("");
			const listaHtml = `
				<div class="club-actividades-list-card">
					<div class="d-flex align-items-center gap-2 mb-2">
						<h6 class="mb-0">${__("Lista de espera (top 5)")}</h6>
						<div class="ms-auto">${this.render_ver_mas_btn(data.ver_mas?.lista_espera_doctype, data.ver_mas?.lista_espera_filters)}</div>
					</div>
					${listaRows ? `<div class="table-responsive"><table class="table table-sm mb-0"><thead><tr><th>${__("Actividad")}</th><th>${__("Grupo / equipo")}</th><th>${__("En espera")}</th><th>${__("Desde")}</th></tr></thead><tbody>${listaRows}</tbody></table></div>` : `<p class="text-muted mb-0">${__("No hay socios en lista de espera.")}</p>`}
				</div>`;
			const infraHtml = `
				<div class="club-actividades-chart-card">
					<h6>${__("Disponibilidad de infraestructura")}</h6>
					<p class="club-actividades-infra-placeholder">${frappe.utils.escape_html(infra.mensaje || __("Próximamente"))}</p>
				</div>`;
			return `
				<div class="club-actividades-charts-row">
					${ocupacionHtml}
				</div>
				<div class="club-actividades-charts-row club-actividades-charts-row--dual">
					${listaHtml}
					${infraHtml}
				</div>
			`;
		},

		mount_dashboard_charts($panel, data) {
			const ocupacion = data.ocupacion_por_deporte || {};
			this._ocupacion_raw = ocupacion.disponible ? ocupacion : null;
			this.mount_ocupacion_chart($panel, ocupacion);
		},

		render_dashboard_filters(actividades) {
			const options = (actividades || [])
				.map(
					(act) =>
						`<option value="${frappe.utils.escape_html(act.name)}" ${act.name === this._dashboard_actividad ? "selected" : ""}>${frappe.utils.escape_html(act.titulo || act.name)}</option>`
				)
				.join("");
			return `
				<div class="club-actividades-dashboard-filters">
					<div class="form-group">
						<label class="small text-muted">${__("Filtrar por actividad")}</label>
						<select class="form-control form-control-sm club-actividades-filter-actividad">
							<option value="">${__("Todas las actividades")}</option>
							${options}
						</select>
					</div>
				</div>
			`;
		},

		render_dashboard($panel, data) {
			this._dashboard = data;
			const actividades = data.actividades_opciones || this._catalog || [];
			$panel.html(`
				<h4 class="mb-2">${__("Gestión de Actividades y Deportes")}</h4>
				${this.render_dashboard_filters(actividades)}
				${this.render_dashboard_quick_actions()}
				${this.render_dashboard_kpis(data)}
				${this.render_dashboard_charts_html(data)}
			`);
			this.mount_dashboard_charts($panel, data);
			this.bind_dashboard_handlers($panel, data);
			this.bind_ocupacion_filtros($panel);
		},

		bind_dashboard_handlers($panel, data) {
			const verMas = data.ver_mas || {};
			$panel.find(".club-actividades-ver-mas").on("click", (e) => {
				const $btn = $(e.currentTarget);
				this.open_list($btn.attr("data-doctype"), $btn.attr("data-filters"));
			});
			$panel.find(".club-actividades-inscribir").on("click", () => {
				frappe.new_doc("Inscripcion Actividad");
			});
			$panel.find(".club-actividades-cupos").on("click", () => {
				frappe.set_route("catalogo-actividades");
			});
			$panel.find(".club-actividades-filter-actividad").on("change", (e) => {
				this._dashboard_actividad = $(e.currentTarget).val() || "";
				this.load_dashboard($(`#${DASHBOARD_ID}`));
			});
		},

		load_dashboard($panel) {
			if (!$panel?.length) return;
			this.render_dashboard_loading($panel);
			frappe.call({
				method: "club_management.activities.api.gestion_actividades_workspace.get_dashboard",
				args: { actividad: this._dashboard_actividad || null },
				callback: (r) => {
					if (!r.message) {
						return;
					}
					this.render_dashboard($panel, r.message);
				},
				error: () => {
					$panel.html(`<p class="text-danger">${__("No se pudo cargar el panel de actividades.")}</p>`);
				},
			});
		},

		render_toolbar() {
			return `
			<div class="club-actividades-toolbar">
				<div class="club-actividades-toolbar-title">
					<h4 class="mb-0">${__("Catálogo de actividades")}</h4>
					<input type="search" class="form-control form-control-sm club-actividades-filter"
						placeholder="${__("Buscar actividad, tira o equipo…")}"
						value="${frappe.utils.escape_html(this._filter || "")}">
				</div>
				<button type="button" class="btn btn-primary btn-sm club-add-actividad">
					+ ${__("Nueva actividad")}
				</button>
			</div>
			${this.render_admin_links()}
		`;
		},

		render_admin_links() {
			const selected = this.get_selected_actividad();
			const actividad_name = selected?.name || "";
			const grupo_name = this._grupo_expandido || "";
			const grupo_filter = actividad_name
				? ` data-filter='${frappe.utils.escape_html(JSON.stringify({ actividad: actividad_name }))}'`
				: "";
			const equipo_filter = grupo_name
				? ` data-filter='${frappe.utils.escape_html(JSON.stringify({ grupo_actividad: grupo_name }))}'`
				: "";

			return `
			<div class="club-actividades-admin">
				<span class="club-actividades-admin-label">${__("Administración")}:</span>
				<nav class="club-actividades-admin-nav" aria-label="${__("Jerarquía Actividad")}">
					<button type="button" class="btn btn-default btn-xs club-open-list"
						data-doctype="Actividad">
						${__("Actividad")}
					</button>
					<span class="club-actividades-admin-sep" aria-hidden="true">›</span>
					<button type="button" class="btn btn-default btn-xs club-open-list"
						data-doctype="Grupo Actividad"${grupo_filter}>
						${__("Grupo / tira")}
					</button>
					<span class="club-actividades-admin-sep" aria-hidden="true">›</span>
					<button type="button" class="btn btn-default btn-xs club-open-list"
						data-doctype="Equipo Actividad"${equipo_filter}>
						${__("Equipo / categoría")}
					</button>
				</nav>
			</div>
		`;
		},

		open_doctype_list(doctype, filters) {
			frappe.route_options = filters || {};
			frappe.set_route("List", doctype);
		},

		render_catalog($panel, data) {
			this._catalog = data.actividades || [];
			this.load_persisted_state();
			const catalog = this.filtered_catalog();
			this.ensure_selected_actividad(catalog);

			if (!catalog.length) {
				const empty_msg = this._catalog.length
					? __("No hay resultados para la búsqueda.")
					: __("No hay actividades habilitadas. Cree la primera con el botón superior.");
				$panel.html(`
					${this.render_toolbar()}
					<p class="text-muted">${empty_msg}</p>
				`);
				this.bind_events($panel);
				return;
			}

			$panel.html(`
				${this.render_toolbar()}
				<div class="club-actividades-accordion">${this.render_actividades_accordion(catalog)}</div>
			`);
			this.bind_events($panel);
			this.restore_view_position($panel);
		},

		capture_view_position($panel) {
			const $accordion = $panel.find(".club-actividades-accordion");
			if ($accordion.length) {
				this._scroll_top = $accordion.scrollTop();
			}
		},

		restore_view_position($panel) {
			const $accordion = $panel.find(".club-actividades-accordion");
			if ($accordion.length && this._scroll_top > 0) {
				$accordion.scrollTop(this._scroll_top);
			}
			if (this._focus_selector) {
				const $target = $panel.find(this._focus_selector).first();
				if ($target.length) {
					$target[0].scrollIntoView({ block: "nearest", behavior: "instant" });
				}
				this._focus_selector = null;
			}
		},

		apply_item_rate_to_row($row, item, callback) {
			if (!item) {
				callback?.();
				return;
			}
			frappe.call({
				method: "club_management.activities.api.gestion_actividades_workspace.get_item_arancel_rate_desk",
				args: { item },
				callback: (r) => {
					const rate = parseFloat(r.message?.rate);
					if (!Number.isNaN(rate) && rate > 0) {
						$row.find(".club-arancel-rate").val(rate);
					}
					callback?.();
				},
				error: () => callback?.(),
			});
		},

		render_actividades_accordion(catalog) {
			return catalog.map((act) => this.render_actividad_accordion(act)).join("");
		},

		render_actividad_accordion(act) {
			const grupos = act.grupos || [];
			const equipos = grupos.reduce((n, g) => n + (g.equipos || []).length, 0);
			const expanded = this._selected_actividad === act.name;
			const arancel_summary = act.item
				? `${act.item} · $${Number(act.rate || 0).toLocaleString()}`
				: __("Sin arancel");
			const meta =
				grupos.length > 0
					? `${grupos.length} ${__("tiras")} · ${equipos} ${__("equipos")}`
					: act.usa_grupos
						? __("Sin tiras")
						: arancel_summary;

			return `
			<div class="club-actividad-card ${expanded ? "is-expanded" : ""}" data-actividad="${frappe.utils.escape_html(act.name)}">
				<button type="button" class="club-actividad-toggle" data-actividad="${frappe.utils.escape_html(act.name)}">
					<span class="club-actividad-chevron">${expanded ? "▾" : "▸"}</span>
					<span class="club-actividad-toggle-text">
						<strong>${frappe.utils.escape_html(act.titulo)}</strong>
						<small class="text-muted">${frappe.utils.escape_html(meta)}</small>
					</span>
				</button>
				<div class="club-actividad-body${expanded ? "" : " is-collapsed"}">
					${this.render_actividad_body(act)}
				</div>
			</div>`;
		},

		render_actividad_body(act) {
			const grupos = act.grupos || [];
			const arancel_row =
				!act.usa_grupos || !grupos.length
					? this.render_arancel_inputs("Actividad", act.name, act.item, act.rate)
					: "";

			const grupos_html = grupos.length
				? grupos.map((g) => this.render_grupo_block(act, g)).join("")
				: `<p class="text-muted small mb-0">${__("Sin grupos / tiras.")}</p>`;

			return `
				<div class="club-actividad-card-header">
					<div class="club-node-actions">
						<button type="button" class="btn btn-default btn-xs club-open-desk"
							data-doctype="Actividad" data-name="${frappe.utils.escape_html(act.name)}">
							${__("Abrir ficha")}
						</button>
						<button type="button" class="btn btn-default btn-xs club-edit-actividad"
							data-name="${frappe.utils.escape_html(act.name)}">
							${__("Editar")}
						</button>
						<button type="button" class="btn btn-warning btn-xs club-disable-actividad"
							data-name="${frappe.utils.escape_html(act.name)}">
							${__("Deshabilitar")}
						</button>
						<button type="button" class="btn btn-default btn-xs club-add-grupo"
							data-actividad="${frappe.utils.escape_html(act.name)}">
							+ ${__("Grupo / tira")}
						</button>
					</div>
				</div>
				${arancel_row}
				<div class="club-grupos-wrap">${grupos_html}</div>`;
		},

		render_grupo_block(act, grupo) {
			const equipos = grupo.equipos || [];
			const expanded = this._grupo_expandido === grupo.name;
			const arancel_summary = grupo.item
				? `${grupo.item} · $${Number(grupo.rate || 0).toLocaleString()}`
				: __("Sin arancel");

			const equipos_html = equipos.length
				? `<div class="club-equipos-table">
					<div class="club-equipos-table-head">
						<span>${__("Equipo / categoría")}</span>
						<span>${__("Acciones")}</span>
					</div>
					${equipos
						.map(
							(eq) => `
					<div class="club-equipo-row">
						<span class="club-equipo-title">${frappe.utils.escape_html(eq.titulo)}</span>
						<div class="club-node-actions club-node-actions--compact">
							<button type="button" class="btn btn-default btn-xs club-open-desk"
								data-doctype="Equipo Actividad" data-name="${frappe.utils.escape_html(eq.name)}"
								title="${__("Abrir ficha")}">↗</button>
							<button type="button" class="btn btn-default btn-xs club-edit-equipo"
								data-name="${frappe.utils.escape_html(eq.name)}"
								data-titulo="${frappe.utils.escape_html(eq.titulo || "")}"
								title="${__("Editar")}">✎</button>
							<button type="button" class="btn btn-warning btn-xs club-disable-equipo"
								data-name="${frappe.utils.escape_html(eq.name)}"
								title="${__("Deshabilitar")}">×</button>
						</div>
					</div>`
						)
						.join("")}
				</div>`
				: `<p class="text-muted small mb-0">${__("Sin equipos.")}</p>`;

			return `
			<div class="club-grupo-card ${expanded ? "is-expanded" : ""}" data-grupo="${frappe.utils.escape_html(grupo.name)}">
				<button type="button" class="club-grupo-toggle" data-grupo="${frappe.utils.escape_html(grupo.name)}">
					<span class="club-grupo-chevron">${expanded ? "▾" : "▸"}</span>
					<span class="club-grupo-toggle-text">
						<strong>${frappe.utils.escape_html(grupo.titulo)}</strong>
						<small class="text-muted">${frappe.utils.escape_html(arancel_summary)} · ${equipos.length} ${__("equipos")}</small>
					</span>
				</button>
				<div class="club-grupo-body${expanded ? "" : " is-collapsed"}">
					<div class="club-grupo-header">
						<div class="club-node-actions">
							<button type="button" class="btn btn-default btn-xs club-open-desk"
								data-doctype="Grupo Actividad" data-name="${frappe.utils.escape_html(grupo.name)}">
								${__("Abrir ficha")}
							</button>
							<button type="button" class="btn btn-default btn-xs club-edit-grupo"
								data-name="${frappe.utils.escape_html(grupo.name)}"
								data-titulo="${frappe.utils.escape_html(grupo.titulo || "")}">
								${__("Editar")}
							</button>
							<button type="button" class="btn btn-warning btn-xs club-disable-grupo"
								data-name="${frappe.utils.escape_html(grupo.name)}">
								${__("Deshabilitar")}
							</button>
							<button type="button" class="btn btn-default btn-xs club-add-equipo"
								data-grupo="${frappe.utils.escape_html(grupo.name)}">
								+ ${__("Equipo")}
							</button>
						</div>
					</div>
					${this.render_arancel_inputs("Grupo Actividad", grupo.name, grupo.item, grupo.rate)}
					<div class="club-equipos-wrap">${equipos_html}</div>
				</div>
			</div>
		`;
		},

		render_arancel_inputs(doctype, name, item, rate) {
			return `
			<div class="club-arancel-row" data-doctype="${frappe.utils.escape_html(doctype)}" data-name="${frappe.utils.escape_html(name)}" data-item="${frappe.utils.escape_html(item || "")}">
				<label class="small text-muted">${__("Ítem arancel")}</label>
				<div class="club-arancel-item-picker">
					<input type="text" class="form-control form-control-sm club-arancel-item" readonly
						value="${frappe.utils.escape_html(item || "")}" placeholder="${__("Seleccionar ítem")}">
					<div class="club-arancel-item-actions">
						<button type="button" class="btn btn-default btn-sm club-pick-arancel-item">
							${__("Buscar")}
						</button>
						<button type="button" class="btn btn-default btn-sm club-create-arancel-item"
							title="${__("Crear ítem de arancel")}" aria-label="${__("Crear ítem de arancel")}">
							+
						</button>
					</div>
				</div>
				<label class="small text-muted">${__("Tarifa")}</label>
				<input type="number" class="form-control form-control-sm club-arancel-rate"
					min="0" step="0.01" value="${frappe.utils.escape_html(String(rate || 0))}">
			</div>
		`;
		},

		item_link_query() {
			return {
				filters: {
					is_stock_item: 0,
					item_group: ["like", "%ICDPE%"],
				},
			};
		},

		show_arancel_item_dialog($row) {
			const panel = this;
			const $input = $row.find(".club-arancel-item");
			const target = {
				set_input(value) {
					const item = (value || "").trim();
					if (!item) {
						return;
					}
					$input.val(item);
					$row.attr("data-item", item);
					panel.apply_item_rate_to_row($row, item, () => panel.save_arancel_row($row));
				},
				$input,
				set_custom_query(args) {
					Object.assign(args, panel.item_link_query());
				},
			};
			new frappe.ui.form.LinkSelector({
				doctype: "Item",
				target,
				txt: ($input.val() || "").trim(),
			});
		},

		show_create_item_dialog($row) {
			const panel = this;
			const rate = parseFloat($row.find(".club-arancel-rate").val()) || 0;
			frappe.prompt(
				[
					{
						fieldname: "item_code",
						label: __("Código"),
						fieldtype: "Data",
						reqd: 1,
					},
					{
						fieldname: "item_name",
						label: __("Nombre"),
						fieldtype: "Data",
						reqd: 1,
					},
					{
						fieldname: "standard_rate",
						label: __("Tarifa"),
						fieldtype: "Float",
						default: rate,
					},
				],
				(values) => {
					frappe.call({
						method: "club_management.activities.api.gestion_actividades_workspace.create_arancel_item_desk",
						args: {
							item_code: values.item_code,
							item_name: values.item_name,
							standard_rate: values.standard_rate || 0,
						},
						freeze: true,
						callback: (r) => {
							if (r.exc || !r.message?.item) {
								return;
							}
							$row.find(".club-arancel-item").val(r.message.item);
							$row.find(".club-arancel-rate").val(r.message.rate || 0);
							$row.attr("data-item", r.message.item);
							panel.save_arancel_row($row);
						},
					});
				},
				__("Crear ítem de arancel"),
				__("Crear y aplicar")
			);
		},

		apply_arancel_to_catalog(result) {
			if (!result?.doctype || !result?.name) {
				return;
			}
			const update_row = (row) => {
				if (row.name !== result.name) {
					return row;
				}
				return { ...row, item: result.item, rate: result.rate };
			};
			this._catalog = (this._catalog || []).map((act) => {
				if (result.doctype === "Actividad") {
					return act.name === result.name
						? { ...act, item: result.item, rate: result.rate }
						: act;
				}
				const grupos = (act.grupos || []).map((grupo) =>
					result.doctype === "Grupo Actividad" ? update_row(grupo) : grupo
				);
				return { ...act, grupos };
			});
		},

		open_desk_form(doctype, name) {
			frappe.set_route("Form", doctype, name);
		},

		prompt_edit_actividad(name) {
			const act = (this._catalog || []).find((row) => row.name === name);
			frappe.prompt(
				[
					{
						fieldname: "titulo",
						label: __("Nombre de la actividad"),
						fieldtype: "Data",
						default: act?.titulo || name,
						reqd: 1,
					},
					{
						fieldname: "usa_grupos",
						label: __("Usa grupos / tiras"),
						fieldtype: "Check",
						default: act?.usa_grupos ? 1 : 0,
					},
					{
						fieldname: "orden",
						label: __("Orden"),
						fieldtype: "Int",
						default: act?.orden || 0,
					},
					{
						fieldname: "descripcion",
						label: __("Descripción"),
						fieldtype: "Small Text",
						default: act?.descripcion || "",
					},
				],
				(values) => {
					frappe.call({
						method: "club_management.activities.api.gestion_actividades_workspace.update_actividad_desk",
						args: {
							name,
							titulo: values.titulo,
							usa_grupos: values.usa_grupos ? 1 : 0,
							orden: values.orden,
							descripcion: values.descripcion,
						},
						freeze: true,
						callback: () => this._after_mutation(),
					});
				},
				__("Editar actividad")
			);
		},

		prompt_edit_grupo(name, titulo) {
			frappe.prompt(
				[
					{
						fieldname: "titulo",
						label: __("Grupo / tira"),
						fieldtype: "Data",
						default: titulo || "",
						reqd: 1,
					},
					{
						fieldname: "orden",
						label: __("Orden"),
						fieldtype: "Int",
						default: 0,
					},
				],
				(values) => {
					frappe.call({
						method: "club_management.activities.api.gestion_actividades_workspace.update_grupo_desk",
						args: {
							name,
							titulo: values.titulo,
							orden: values.orden,
						},
						freeze: true,
						callback: () => this._after_mutation(),
					});
				},
				__("Editar grupo / tira")
			);
		},

		prompt_edit_equipo(name, titulo) {
			frappe.prompt(
				[
					{
						fieldname: "titulo",
						label: __("Equipo / categoría"),
						fieldtype: "Data",
						default: titulo || "",
						reqd: 1,
					},
					{
						fieldname: "orden",
						label: __("Orden"),
						fieldtype: "Int",
						default: 0,
					},
				],
				(values) => {
					frappe.call({
						method: "club_management.activities.api.gestion_actividades_workspace.update_equipo_desk",
						args: {
							name,
							titulo: values.titulo,
							orden: values.orden,
						},
						freeze: true,
						callback: () => this._after_mutation(),
					});
				},
				__("Editar equipo / categoría")
			);
		},

		confirm_disable(method, name, label) {
			frappe.confirm(
				__("¿Deshabilitar {0}? Dejará de aparecer en inscripciones.", [label]),
				() => {
					frappe.call({
						method,
						args: { name, habilitada: 0 },
						freeze: true,
						callback: () => this._after_mutation(),
					});
				}
			);
		},

		_after_mutation(focus_selector) {
			this._focus_selector = focus_selector || null;
			this._refresh_catalog();
		},

		_refresh_catalog() {
			if (!this.is_actividades_workspace()) {
				return;
			}
			const $panel = $(`#${PANEL_ID}`);
			if (!$panel.length) {
				this.refresh();
				return;
			}
			this.capture_view_position($panel);
			this.load_persisted_state();
			frappe.call({
				method: "club_management.activities.api.gestion_actividades_workspace.get_catalog",
				callback: (r) => {
					if (r.message) {
						this.render_catalog($panel, r.message);
					}
				},
				error: () => {
					frappe.show_alert({
						message: __("No se pudo actualizar el catálogo."),
						indicator: "red",
					});
				},
			});
		},

		bind_events($panel) {
			const panel = this;

			$panel.off(".club-actividades");

			$panel.on("input.club-actividades", ".club-actividades-filter", function () {
				panel._filter = $(this).val() || "";
				panel.render_catalog($panel, { actividades: panel._catalog });
			});

			$panel.on("click.club-actividades", ".club-actividad-toggle", function (e) {
				e.preventDefault();
				const actividad = $(this).attr("data-actividad");
				panel._selected_actividad = panel._selected_actividad === actividad ? null : actividad;
				panel._grupo_expandido = null;
				panel.persist_state();
				panel.render_catalog($panel, { actividades: panel._catalog });
			});

			$panel.on("click.club-actividades", ".club-grupo-toggle", function (e) {
				e.preventDefault();
				e.stopPropagation();
				const grupo = $(this).attr("data-grupo");
				panel._grupo_expandido = panel._grupo_expandido === grupo ? null : grupo;
				panel.persist_state();
				panel.render_catalog($panel, { actividades: panel._catalog });
			});

			$panel.on("click.club-actividades", ".club-add-actividad", () => {
				frappe.prompt(
					[
						{
							fieldname: "titulo",
							label: __("Nombre de la actividad"),
							fieldtype: "Data",
							reqd: 1,
						},
						{
							fieldname: "usa_grupos",
							label: __("Usa grupos / tiras"),
							fieldtype: "Check",
							default: 0,
						},
					],
					(values) => {
						frappe.call({
							method: "club_management.activities.api.gestion_actividades_workspace.create_actividad_desk",
							args: {
								titulo: values.titulo,
								usa_grupos: values.usa_grupos ? 1 : 0,
							},
							freeze: true,
							callback: (r) => {
								if (r.message?.name) {
									panel._selected_actividad = r.message.name;
									panel._grupo_expandido = null;
									panel.persist_state();
								}
								panel._after_mutation(
									r.message?.name
										? `.club-actividad-card[data-actividad="${r.message.name}"]`
										: null
								);
							},
						});
					},
					__("Nueva actividad")
				);
			});

			$panel.on("click.club-actividades", ".club-add-grupo", (e) => {
				const actividad = $(e.currentTarget).data("actividad");
				frappe.prompt(
					[{ fieldname: "titulo", label: __("Grupo / tira"), fieldtype: "Data", reqd: 1 }],
					(values) => {
						frappe.call({
							method: "club_management.activities.api.gestion_actividades_workspace.create_grupo_desk",
							args: { actividad, titulo: values.titulo },
							freeze: true,
							callback: (r) => {
								panel._selected_actividad = actividad;
								if (r.message?.name) {
									panel._grupo_expandido = r.message.name;
								}
								panel.persist_state();
								panel._after_mutation(
									r.message?.name
										? `.club-grupo-card[data-grupo="${r.message.name}"]`
										: `.club-actividad-card[data-actividad="${actividad}"]`
								);
							},
						});
					},
					__("Nuevo grupo / tira")
				);
			});

			$panel.on("click.club-actividades", ".club-add-equipo", (e) => {
				const grupo_actividad = $(e.currentTarget).data("grupo");
				frappe.prompt(
					[{ fieldname: "titulo", label: __("Equipo / categoría"), fieldtype: "Data", reqd: 1 }],
					(values) => {
						frappe.call({
							method: "club_management.activities.api.gestion_actividades_workspace.create_equipo_desk",
							args: { grupo_actividad, titulo: values.titulo },
							freeze: true,
							callback: (r) => {
								panel._grupo_expandido = grupo_actividad;
								const actividad = (panel._catalog || []).find((row) =>
									(row.grupos || []).some((grupo) => grupo.name === grupo_actividad)
								);
								if (actividad) {
									panel._selected_actividad = actividad.name;
								}
								panel.persist_state();
								panel._after_mutation(
									`.club-grupo-card[data-grupo="${grupo_actividad}"]`
								);
							},
						});
					},
					__("Nuevo equipo / categoría")
				);
			});

			$panel.on("blur.club-actividades", ".club-arancel-rate", (e) => {
				panel.save_arancel_row($(e.currentTarget).closest(".club-arancel-row"));
			});

			$panel.on("click.club-actividades", ".club-pick-arancel-item, .club-arancel-item", (e) => {
				e.preventDefault();
				e.stopPropagation();
				panel.show_arancel_item_dialog($(e.currentTarget).closest(".club-arancel-row"));
			});

			$panel.on("click.club-actividades", ".club-create-arancel-item", (e) => {
				e.preventDefault();
				e.stopPropagation();
				panel.show_create_item_dialog($(e.currentTarget).closest(".club-arancel-row"));
			});

			$panel.on("click.club-actividades", ".club-open-list", (e) => {
				const $btn = $(e.currentTarget);
				let filters = {};
				const raw = $btn.attr("data-filter");
				if (raw) {
					try {
						filters = JSON.parse(raw);
					} catch (_err) {
						filters = {};
					}
				}
				panel.open_doctype_list($btn.data("doctype"), filters);
			});

			$panel.on("click.club-actividades", ".club-open-desk", (e) => {
				const $btn = $(e.currentTarget);
				panel.open_desk_form($btn.data("doctype"), $btn.data("name"));
			});

			$panel.on("click.club-actividades", ".club-edit-actividad", (e) => {
				panel.prompt_edit_actividad($(e.currentTarget).data("name"));
			});

			$panel.on("click.club-actividades", ".club-edit-grupo", (e) => {
				const $btn = $(e.currentTarget);
				panel.prompt_edit_grupo($btn.data("name"), $btn.data("titulo"));
			});

			$panel.on("click.club-actividades", ".club-edit-equipo", (e) => {
				const $btn = $(e.currentTarget);
				panel.prompt_edit_equipo($btn.data("name"), $btn.data("titulo"));
			});

			$panel.on("click.club-actividades", ".club-disable-actividad", (e) => {
				const name = $(e.currentTarget).data("name");
				panel.confirm_disable(
					"club_management.activities.api.gestion_actividades_workspace.update_actividad_desk",
					name,
					name
				);
			});

			$panel.on("click.club-actividades", ".club-disable-grupo", (e) => {
				const name = $(e.currentTarget).data("name");
				panel.confirm_disable(
					"club_management.activities.api.gestion_actividades_workspace.update_grupo_desk",
					name,
					name
				);
			});

			$panel.on("click.club-actividades", ".club-disable-equipo", (e) => {
				const name = $(e.currentTarget).data("name");
				panel.confirm_disable(
					"club_management.activities.api.gestion_actividades_workspace.update_equipo_desk",
					name,
					name
				);
			});
		},

		save_arancel_row($row) {
			const doctype = $row.attr("data-doctype");
			const name = $row.attr("data-name");
			const item = (
				$row.find(".club-arancel-item").val() ||
				$row.attr("data-item") ||
				""
			).trim();
			const rate = parseFloat($row.find(".club-arancel-rate").val());
			if (!doctype || !name) {
				return;
			}
			if (!item && Number.isNaN(rate)) {
				return;
			}
			if (!item) {
				frappe.show_alert({
					message: __("Seleccione un ítem de arancel antes de guardar la tarifa."),
					indicator: "orange",
				});
				return;
			}
			frappe.call({
				method: "club_management.activities.api.gestion_actividades_workspace.set_arancel_desk",
				args: {
					doctype,
					name,
					item,
					rate: Number.isNaN(rate) ? 0 : rate,
				},
				callback: (r) => {
					if (!r.message) {
						return;
					}
					this.apply_arancel_to_catalog(r.message);
					frappe.show_alert({ message: __("Arancel actualizado"), indicator: "green" });
					const $panel = $(`#${PANEL_ID}`);
					if ($panel.length) {
						this.render_catalog($panel, { actividades: this._catalog });
					}
				},
			});
		},

		refresh() {
			if (this.is_catalog_page()) {
				this.clear_mount();
				return;
			}
			if (!this.is_actividades_workspace()) {
				this.clear_mount();
				return;
			}
			club_management.secretaria_panel?.clear_mount?.();
			club_management.actividades_sidebar?.refresh?.();
			const $parent = this.get_mount_parent();
			if (!$parent) {
				this.schedule_refresh();
				return;
			}
			const $dash = this.ensure_dashboard_mount($parent);
			this.load_dashboard($dash);
		},
	};

	frappe.router.on("change", () => {
		if (!club_management.actividades_panel.is_actividades_workspace()) {
			club_management.actividades_panel.clear_mount();
		}
		club_management.actividades_panel.schedule_refresh();
	});

	$(document).on("page-change app_ready", () => {
		club_management.actividades_panel.schedule_refresh();
	});
})();
