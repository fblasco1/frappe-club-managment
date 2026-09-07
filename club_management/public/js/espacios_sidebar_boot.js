/* global frappe */

(function () {
	frappe.provide("club_management.espacios_sidebar");

	const SIDEBAR_KEY = "espacios";
	const ITEMS = [
		{
			label: __("Dashboard principal"),
			type: "Link",
			link_type: "Workspace",
			link_to: "Espacios",
			icon: "home",
		},
		{
			label: __("Ocupación de espacios"),
			type: "Link",
			link_type: "Page",
			link_to: "ocupacion-espacios",
			icon: "calendar",
		},
	];

	club_management.espacios_sidebar.is_spaces_route = function () {
		const route = frappe.get_route() || [];
		if (route[0] === "Workspaces" && route[1] === "Espacios") {
			return true;
		}
		return route.length === 1 && ["espacios", "ocupacion-espacios"].includes(route[0]);
	};

	club_management.espacios_sidebar.ensure_boot = function () {
		const boot = frappe.boot.workspace_sidebar_item || {};
		frappe.boot.workspace_sidebar_item = boot;
		boot[SIDEBAR_KEY] = {
			label: __("Espacios"),
			items: ITEMS,
			header_icon: "organization",
			module: "Spaces",
			app: "club_management",
		};
	};

	club_management.espacios_sidebar.refresh = function () {
		if (!this.is_spaces_route()) {
			return;
		}
		this.ensure_boot();
		frappe.app?.sidebar?.setup?.(__("Espacios"));
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
