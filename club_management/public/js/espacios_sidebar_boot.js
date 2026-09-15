/* global frappe */

(function () {
	frappe.provide("club_management.espacios_sidebar");

	const SIDEBAR_KEY = "espacios";
	const WORKSPACE_LABEL = __("Gestión de Espacios y Canchas");
	const ITEMS = [
		{
			label: __("Inicio Espacios"),
			type: "Link",
			link_type: "Page",
			link_to: "espacios",
			icon: "home",
		},
		{
			label: __("Ocupación (planilla)"),
			type: "Link",
			link_type: "Page",
			link_to: "ocupacion-espacios",
			icon: "calendar",
		},
		{
			label: __("Catálogo de espacios"),
			type: "Link",
			link_type: "DocType",
			link_to: "Espacio",
			icon: "organization",
		},
		{
			label: __("Reservas"),
			type: "Link",
			link_type: "DocType",
			link_to: "Reserva Espacio",
			icon: "list",
		},
	];

	club_management.espacios_sidebar.is_spaces_route = function () {
		const route = frappe.get_route() || [];
		if (route[0] === "Workspaces") {
			const name = (route[1] || "").toLowerCase();
			if (name === "espacios" || name.includes("espacios") || name.includes("canchas")) {
				return true;
			}
		}
		if (route[0] === "List" || route[0] === "Form") {
			return ["Espacio", "Reserva Espacio"].includes(route[1]);
		}
		return route.length === 1 && ["espacios", "ocupacion-espacios"].includes(route[0]);
	};

	club_management.espacios_sidebar.apply_light_layout = function (enabled) {
		const body = document.body;
		if (!body) {
			return;
		}
		// Compat: class específica Espacios. El tema claro unificado lo aplica club_desk_navigation.
		body.classList.toggle("club-espacios-route", !!enabled);
	};

	club_management.espacios_sidebar.ensure_boot = function () {
		const boot = frappe.boot.workspace_sidebar_item || {};
		frappe.boot.workspace_sidebar_item = boot;
		boot[SIDEBAR_KEY] = {
			label: WORKSPACE_LABEL,
			items: ITEMS,
			header_icon: "organization",
			module: "Spaces",
			app: "club_management",
		};
		boot["gestión de espacios y canchas"] = boot[SIDEBAR_KEY];
	};

	club_management.espacios_sidebar.refresh = function () {
		const on_spaces = this.is_spaces_route();
		this.apply_light_layout(on_spaces);
		if (!on_spaces) {
			return;
		}
		this.ensure_boot();
		frappe.app?.sidebar?.setup?.(SIDEBAR_KEY);
	};

	club_management.espacios_sidebar.schedule_refresh = function () {
		clearTimeout(this._refresh_timer);
		this._refresh_timer = setTimeout(() => this.refresh(), 120);
	};

	$(document).on("page-change app_ready", () => {
		club_management.espacios_sidebar.schedule_refresh();
	});
	frappe.router.on("change", () => {
		club_management.espacios_sidebar.schedule_refresh();
	});
})();
