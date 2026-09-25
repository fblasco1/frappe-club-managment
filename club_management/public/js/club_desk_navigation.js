/* global frappe */

(function () {

	frappe.provide("club_management.club_desk_navigation");



	const NAV_ID = "club-desk-nav";

	const PANEL_ROLES = new Set([
		"Secretaria",
		"Coordinacion",
		"Tesoreria",
		"System Manager",
	]);

	const HIDDEN_WORKSPACES = new Set(["Inicio", "Inicio Club"]);



	club_management.club_desk_navigation.TABS = [

		{

			label: __("Gestión de Socios"),

			workspace: "Socios",

			icon: "users",

			tab: "socios",

			type: "workspace",

		},

		{

			label: __("Gestión de Actividades y Deportes"),

			workspace: "Gestión de Actividades",

			icon: "activity",

			tab: "actividades",

			type: "workspace",

		},

		{

			label: __("Gestión de Espacios y Canchas"),

			workspace: "Gestión de Espacios y Canchas",

			icon: "organization",

			tab: "espacios",

			type: "workspace",

		},

		{

			label: __("Tesorería"),

			workspace: "Tesorería",

			icon: "currency-exchange",

			emoji: "🏦",

			tab: "tesoreria",

			type: "workspace",

		},

	];



	club_management.club_desk_navigation.CLUB_REPORTS = new Set([

		"Cobranza por fechas",

		"Pagos por equipo",

		"Deuda por actividad",

	]);



	club_management.club_desk_navigation.CLUB_REPORTS_SOCIOS = new Set([

		"Cobranza por fechas",

		"Pagos por equipo",

		"Deuda por actividad",

	]);



	club_management.club_desk_navigation.CLUB_REPORTS_ACTIVIDADES = new Set([

		"Cobranza por fechas",

		"Pagos por equipo",

		"Deuda por actividad",

	]);



	club_management.club_desk_navigation.CLUB_PAGES = new Set([

		"valores-cuota-social",

		"catalogo-actividades",

		"espacios",

		"ocupacion-espacios",

	]);



	club_management.club_desk_navigation.CLUB_PAGES_SOCIOS = new Set([

		"valores-cuota-social",

	]);



	club_management.club_desk_navigation.CLUB_PAGES_ACTIVIDADES = new Set([

		"catalogo-actividades",

	]);



	club_management.club_desk_navigation.CLUB_PAGES_ESPACIOS = new Set([

		"espacios",

		"ocupacion-espacios",

	]);



	club_management.club_desk_navigation.CLUB_SOCIOS_DOCTYPES = new Set(["Socio"]);



	club_management.club_desk_navigation.CLUB_ACTIVIDADES_DOCTYPES = new Set([

		"Actividad",

		"Grupo Actividad",

		"Equipo Actividad",

		"Inscripcion Actividad",

	]);



	club_management.club_desk_navigation.CLUB_ESPACIOS_DOCTYPES = new Set([

		"Espacio",

		"Reserva Espacio",

	]);



	club_management.club_desk_navigation.SLUG_ALIASES = {

		secretaria: "Socios",

		"gestion-de-actividades": "Gestión de Actividades",
		"gestión-de-actividades": "Gestión de Actividades",

		"gestion-de-espacios-y-canchas": "Gestión de Espacios y Canchas",
		"gestión-de-espacios-y-canchas": "Gestión de Espacios y Canchas",

		"gestion-de-socios": "Socios",

		"inicio-club": "Socios",

		inicio: "Socios",

	};



	club_management.club_desk_navigation._refresh_timer = null;
	club_management.club_desk_navigation._search_timer = null;



	club_management.club_desk_navigation.workspace_slug = function (workspace) {

		if (!workspace) {

			return "";

		}

		return frappe.router.slug(workspace);

	};



	/** Quita diacríticos (gestión → gestion). `frappe.router.slug` no lo hace. */

	club_management.club_desk_navigation.fold_slug_key = function (value) {

		const base = String(value || "");

		try {

			return base.normalize("NFD").replace(/\p{M}/gu, "");

		} catch (e) {

			return base;

		}

	};



	/** Resuelve alias de ruta corta ASCII o con tilde (prod vs local). */

	club_management.club_desk_navigation.resolve_slug_alias = function (segment) {

		if (!segment) {

			return null;

		}

		const raw = String(segment);

		const slug = this.workspace_slug(raw);

		const folded = this.fold_slug_key(slug || raw);

		return (

			this.SLUG_ALIASES[raw] ||

			this.SLUG_ALIASES[slug] ||

			this.SLUG_ALIASES[folded] ||

			null

		);

	};



	club_management.club_desk_navigation.get_club_workspace_name = function () {

		const route = frappe.get_route() || [];

		if (route[0] === "Workspaces" && route[1]) {

			return route[1] === "private" ? route[2] : route[1];

		}

		const page = frappe.workspace?.page || frappe.workspace?._page;

		if (page?.name && this.TABS.some((tab) => tab.workspace === page.name)) {

			return page.name;

		}

		// Ruta de un solo segmento (p. ej. /desk/tesorería o /desk/gestión-de-actividades).
		if (route.length === 1 && route[0]) {

			const alias = this.resolve_slug_alias(route[0]);
			if (alias) {
				return alias;
			}

			const key = this.workspace_slug(route[0]);
			const folded = this.fold_slug_key(key);

			if (key && frappe.workspaces?.[key]) {

				return frappe.workspaces[key].name;

			}

			if (folded && frappe.workspaces?.[folded]) {

				return frappe.workspaces[folded].name;

			}

		}

		return null;

	};



	club_management.club_desk_navigation.get_active_report = function () {

		const route = frappe.get_route() || [];

		if (route[0] === "query-report" && route[1]) {

			return route[1];

		}

		return null;

	};



	club_management.club_desk_navigation.get_active_doctype = function () {

		const route = frappe.get_route() || [];

		if ((route[0] === "List" || route[0] === "Form") && route[1]) {

			return route[1];

		}

		return null;

	};



	club_management.club_desk_navigation.get_active_page = function () {

		const route = frappe.get_route() || [];

		if (route.length === 1 && route[0] && this.CLUB_PAGES.has(route[0])) {

			return route[0];

		}

		return null;

	};



	club_management.club_desk_navigation.is_club_page = function (page_name) {

		const active = page_name || this.get_active_page();

		return active ? this.CLUB_PAGES.has(active) : false;

	};



	club_management.club_desk_navigation.is_club_socio_page = function () {

		const doctype = this.get_active_doctype();

		return doctype ? this.CLUB_SOCIOS_DOCTYPES.has(doctype) : false;

	};



	club_management.club_desk_navigation.is_club_actividad_page = function () {

		const doctype = this.get_active_doctype();

		return doctype ? this.CLUB_ACTIVIDADES_DOCTYPES.has(doctype) : false;

	};



	club_management.club_desk_navigation.is_club_espacio_page = function () {

		const doctype = this.get_active_doctype();

		return doctype ? this.CLUB_ESPACIOS_DOCTYPES.has(doctype) : false;

	};



	club_management.club_desk_navigation.is_club_workspace = function (workspace_name) {

		const active = workspace_name || this.get_club_workspace_name();

		return (

			active === "Socios" ||

			active === "Gestión de Actividades" ||

			active === "Gestión de Espacios y Canchas" ||

			active === "Tesorería"

		);

	};



	club_management.club_desk_navigation.is_club_report = function (report_name) {

		const active = report_name || this.get_active_report();

		return active ? this.CLUB_REPORTS.has(active) : false;

	};



	club_management.club_desk_navigation.is_club_desk_page = function () {

		return (

			this.is_club_workspace() ||

			this.is_club_report() ||

			this.is_club_socio_page() ||

			this.is_club_actividad_page() ||

			this.is_club_espacio_page() ||

			this.is_club_page()

		);

	};



	club_management.club_desk_navigation.get_active_tab = function () {

		const report = this.get_active_report();

		if (report && this.CLUB_REPORTS.has(report)) {

			return this.TABS.find((tab) => tab.tab === "socios") || null;

		}

		if (this.is_club_socio_page()) {

			return this.TABS.find((tab) => tab.workspace === "Socios") || null;

		}

		if (this.is_club_actividad_page()) {

			return this.TABS.find((tab) => tab.tab === "actividades") || null;

		}

		if (this.is_club_espacio_page()) {

			return this.TABS.find((tab) => tab.tab === "espacios") || null;

		}

		if (this.is_club_page()) {

			const page = this.get_active_page();

			if (page && this.CLUB_PAGES_ACTIVIDADES?.has(page)) {

				return this.TABS.find((tab) => tab.tab === "actividades") || null;

			}

			if (page && this.CLUB_PAGES_ESPACIOS?.has(page)) {

				return this.TABS.find((tab) => tab.tab === "espacios") || null;

			}

			return this.TABS.find((tab) => tab.tab === "socios") || null;

		}

		const workspace = this.get_club_workspace_name();

		return this.TABS.find((tab) => tab.workspace === workspace) || null;

	};



	club_management.club_desk_navigation.navigate_to_workspace = function (workspace) {

		if (!workspace || HIDDEN_WORKSPACES.has(workspace)) {

			return;

		}

		// Espacios: el dashboard operativo es la Page `/desk/espacios` (no el workspace de shortcuts).
		if (workspace === "Gestión de Espacios y Canchas") {
			const route = frappe.get_route() || [];
			if (route.length === 1 && route[0] === "espacios") {
				club_management.espacios_sidebar?.refresh?.();
				return;
			}
			frappe.route_flags.replace_route = true;
			frappe.set_route("espacios");
			club_management.espacios_sidebar?.refresh?.();
			return;
		}

		const slug = this.workspace_slug(workspace);

		const ws_meta = frappe.workspaces?.[slug];

		if (!ws_meta) {

			frappe.show_alert({

				message: __("No tiene acceso al workspace {0}", [workspace]),

				indicator: "red",

			});

			return;

		}

		if (frappe.workspace?._page?.name === workspace) {

			return;

		}

		frappe.route_flags.replace_route = true;

		const show = () => {

			frappe.workspace?.show_page?.({ name: workspace, public: ws_meta.public });

		};

		const routed = frappe.set_route("Workspaces", workspace);

		if (routed && typeof routed.then === "function") {

			routed.then(show);

		} else {

			setTimeout(show, 80);

		}

		if (workspace === "Socios") {

			club_management.secretaria_sidebar?.refresh?.();

		} else if (workspace === "Gestión de Actividades") {

			club_management.actividades_sidebar?.refresh?.();

		}

	};



	club_management.club_desk_navigation.navigate_to_report = function (report) {

		if (!report || !this.CLUB_REPORTS.has(report)) {

			return;

		}

		frappe.set_route("query-report", report);

	};



	club_management.club_desk_navigation.redirect_slug_aliases = function () {

		const sub_path = (frappe.router?.current_sub_path || "").replace(/\/$/, "");

		if (!sub_path) {

			return;

		}

		const parts = sub_path.split("/");

		if (parts[0] === "Workspaces" && parts[1]) {

			const workspace = decodeURIComponent(parts[1].replace(/\+/g, " "));

			if (HIDDEN_WORKSPACES.has(workspace)) {

				this.navigate_to_workspace("Socios");

				return;

			}

			// Workspace Espacios → dashboard Page (pendientes + agenda del día).
			if (workspace === "Gestión de Espacios y Canchas") {
				frappe.route_flags.replace_route = true;
				frappe.set_route("espacios");
				return;
			}

			return;

		}

		if (parts.length !== 1) {

			return;

		}

		// Prod puede servir /desk/gestión-de-actividades (tilde) con bundle que solo
		// tenía la clave ASCII; plegar diacríticos antes del lookup.
		const workspace_name = this.resolve_slug_alias(decodeURIComponent(parts[0]));

		if (workspace_name) {

			this.navigate_to_workspace(workspace_name);

		}

	};



	club_management.club_desk_navigation.get_mount_parent = function () {

		if (
			this.is_club_report() ||
			this.is_club_socio_page() ||
			this.is_club_actividad_page() ||
			this.is_club_espacio_page() ||
			this.is_club_page()
		) {

			const candidates = [
				club_management.espacios_dashboard_page?.page?.main,
				club_management.ocupacion_espacios_page?.page?.main,
				typeof cur_list !== "undefined" ? cur_list?.page?.main : null,
				typeof cur_frm !== "undefined" ? cur_frm?.page?.main : null,
				frappe.query_report?.page?.main,
				cur_page?.page?.main,
				frappe.container?.page?.main,
			];

			for (const candidate of candidates) {
				if (candidate?.length && candidate.closest("body").length) {
					return candidate;
				}
			}

			const $section = $(".page-container:visible .layout-main-section, .page-content:visible")
				.filter(":visible")
				.first();

			if ($section.length) {
				return $section;
			}

		}

		const ws = frappe.workspace;

		if (ws?.body?.length) {

			return ws.body;

		}

		return null;

	};



	club_management.club_desk_navigation.clear_mount = function () {

		$(`#${NAV_ID}`).remove();

		$(".layout-main-section, .page-content").removeClass("club-desk-with-nav");

		frappe.workspace?.body?.removeClass("club-desk-with-nav");

	};



	club_management.club_desk_navigation.render_nav = function () {

		if (!this.has_panel_role()) {

			this.clear_mount();

			return;

		}

		if (!this.is_club_desk_page()) {

			this.clear_mount();

			return;

		}



		const $parent = this.get_mount_parent();

		if (!$parent?.length) {

			this.schedule_refresh();

			return;

		}



		$(".club-desk-with-nav").not($parent).removeClass("club-desk-with-nav");
		$parent.addClass("club-desk-with-nav");

		const active_tab = this.get_active_tab();

		let $nav = $(`#${NAV_ID}`);

		if (!$nav.length) {
			$nav = $(
				`<nav id="${NAV_ID}" class="club-desk-nav" aria-label="${__("Navegación")}"></nav>`
			);
		}

		// Siempre reparentar al mount visible (Workspace ↔ Page ↔ List).
		$parent.prepend($nav);



		const tabs_html = this.TABS.map((tab) => {

			const is_active = active_tab?.tab === tab.tab;

			const icon = tab.emoji
				? `<span class="club-desk-nav-emoji" aria-hidden="true">${tab.emoji}</span>`
				: frappe.utils.icon(tab.icon, "sm", "", "", "club-desk-nav-icon");

			const data_attrs = `data-nav-type="workspace" data-workspace="${frappe.utils.escape_html(tab.workspace)}"`;

			return `

			<button

				type="button"

				class="club-desk-nav-tab club-desk-nav-tab--${tab.tab} ${is_active ? "is-active" : ""}"

				${data_attrs}

				${is_active ? 'aria-current="page"' : ""}

			>

				${icon}

				<span>${frappe.utils.escape_html(tab.label)}</span>

			</button>

		`;

		}).join("");



		$nav.html(`<div class="club-desk-nav-inner">${tabs_html}
			<div class="club-desk-nav-search-wrap">
				<input type="search" class="form-control form-control-sm club-desk-nav-search"
					placeholder="${__("Buscar socio por DNI o apellido…")}" autocomplete="off" aria-label="${__("Buscar socio")}">
				<div class="club-desk-nav-search-results" role="listbox"></div>
			</div>
		</div>`);

		$nav.find('[data-workspace="Inicio"], [data-workspace="Inicio Club"]').remove();

		this.bind_nav_tab_handlers($nav);
		this.bind_nav_search_handlers($nav);
	};



	club_management.club_desk_navigation.bind_nav_search_handlers = function ($nav) {
		const nav = club_management.club_desk_navigation;
		const $input = $nav.find(".club-desk-nav-search");
		const $results = $nav.find(".club-desk-nav-search-results");

		const close_results = () => {
			$results.removeClass("is-open").empty();
		};

		$input.off("input.club_search").on("input.club_search", function () {
			clearTimeout(nav._search_timer);
			const query = ($(this).val() || "").trim();
			if (query.length < 2) {
				close_results();
				return;
			}
			nav._search_timer = setTimeout(() => {
				frappe.call({
					method: "club_management.members.api.club_desk.search_socio_desk",
					args: { query, limit: 8 },
					callback: (r) => {
						const rows = r.message || [];
						if (!rows.length) {
							$results
								.html(`<div class="text-muted small p-2">${__("Sin resultados")}</div>`)
								.addClass("is-open");
							return;
						}
						const html = rows
							.map(
								(row) => `
							<button type="button" class="club-desk-nav-search-item" data-name="${frappe.utils.escape_html(row.name)}" role="option">
								${frappe.utils.escape_html(row.label)}
							</button>`
							)
							.join("");
						$results.html(html).addClass("is-open");
					},
				});
			}, 250);
		});

		$results.off("click.club_search").on("click.club_search", ".club-desk-nav-search-item", function () {
			const name = $(this).attr("data-name");
			close_results();
			$input.val("");
			if (name) {
				frappe.set_route("Form", "Socio", name);
			}
		});

		$(document).off("click.club_search_outside").on("click.club_search_outside", (event) => {
			if (!$(event.target).closest(".club-desk-nav-search-wrap").length) {
				close_results();
			}
		});
	};



	club_management.club_desk_navigation.bind_nav_tab_handlers = function ($nav) {

		const nav = club_management.club_desk_navigation;

		$nav

			.find(".club-desk-nav-tab")

			.off("click.club_nav")

			.on("click.club_nav", function (event) {

				event.preventDefault();

				event.stopImmediatePropagation();

				const workspace = $(this).attr("data-workspace");

				if (!workspace || HIDDEN_WORKSPACES.has(workspace)) {

					return;

				}

				if (workspace === "Gestión de Espacios y Canchas") {
					const route = frappe.get_route() || [];
					if (route.length === 1 && route[0] === "espacios") {
						return;
					}
				} else if (workspace === nav.get_club_workspace_name() && !nav.get_active_report()) {

					return;

				}

				nav.navigate_to_workspace(workspace);

			});

	};



	club_management.club_desk_navigation.has_panel_role = function () {

		return (frappe.user_roles || []).some((role) => PANEL_ROLES.has(role));

	};



	club_management.club_desk_navigation.refresh_sidebar = function () {

		if (!this.has_panel_role()) {

			return;

		}

		const report = this.get_active_report();

		if (report && this.CLUB_REPORTS.has(report)) {

			club_management.secretaria_sidebar?.refresh?.();

			return;

		}

		if (this.is_club_socio_page()) {

			club_management.secretaria_sidebar?.refresh?.();

			return;

		}

		if (this.is_club_actividad_page()) {

			club_management.actividades_sidebar?.refresh?.();

			return;

		}

		if (this.is_club_espacio_page()) {

			club_management.espacios_sidebar?.refresh?.();

			return;

		}

		const page = this.get_active_page();

		if (page && this.CLUB_PAGES_SOCIOS?.has(page)) {

			club_management.secretaria_sidebar?.refresh?.();

			return;

		}

		if (page && this.CLUB_PAGES_ACTIVIDADES?.has(page)) {

			club_management.actividades_sidebar?.refresh?.();

			return;

		}

		if (page && this.CLUB_PAGES_ESPACIOS?.has(page)) {

			club_management.espacios_sidebar?.refresh?.();

			return;

		}

		const workspace = this.get_club_workspace_name();

		if (workspace === "Socios") {

			club_management.secretaria_sidebar?.refresh?.();

		} else if (workspace === "Gestión de Actividades") {

			club_management.actividades_sidebar?.refresh?.();

		} else if (workspace === "Gestión de Espacios y Canchas") {

			club_management.espacios_sidebar?.refresh?.();

		}

	};



	club_management.club_desk_navigation.refresh = function () {

		this.redirect_slug_aliases();

		this.apply_portal_theme();

		this.render_nav();

		this.refresh_sidebar();

	};



	club_management.club_desk_navigation.PORTAL_ACCENTS = [
		"socios",
		"actividades",
		"espacios",
		"tesoreria",
	];

	club_management.club_desk_navigation.apply_portal_theme = function () {
		const body = document.body;
		if (!body) {
			return;
		}

		const enabled = this.has_panel_role() && this.is_club_desk_page();
		body.classList.toggle("club-portal-theme", !!enabled);

		this.PORTAL_ACCENTS.forEach((accent) => {
			body.classList.remove(`club-portal--${accent}`);
		});

		if (enabled) {
			const tab = this.get_active_tab()?.tab || "socios";
			if (this.PORTAL_ACCENTS.includes(tab)) {
				body.classList.add(`club-portal--${tab}`);
			}

			body.setAttribute("data-theme-override", "light");
			if (!body.dataset.clubPrevTheme) {
				body.dataset.clubPrevTheme =
					document.documentElement.getAttribute("data-theme") || "";
			}
			document.documentElement.setAttribute("data-theme", "light");
			return;
		}

		if (body.hasAttribute("data-theme-override")) {
			const prev = body.dataset.clubPrevTheme || "";
			body.removeAttribute("data-theme-override");
			delete body.dataset.clubPrevTheme;
			if (prev) {
				document.documentElement.setAttribute("data-theme", prev);
			} else {
				document.documentElement.removeAttribute("data-theme");
			}
		}
	};

	club_management.club_desk_navigation.schedule_refresh = function () {

		clearTimeout(this._refresh_timer);

		this._refresh_timer = setTimeout(() => this.refresh(), 120);

	};



	$(document).on("page-change app_ready", () => {
		club_management.club_desk_navigation.redirect_slug_aliases();
		club_management.club_desk_navigation.schedule_refresh();
	});

	frappe.router.on("change", () => {
		club_management.club_desk_navigation.schedule_refresh();
	});

})();

