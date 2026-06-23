/* global frappe */

(function () {
	frappe.provide("club_management.secretaria_sidebar");

	const SIDEBAR_KEY = "secretaría";

	const SIDEBAR_ITEMS = [
		{
			label: __("Secretaría"),
			type: "Link",
			link_type: "Workspace",
			link_to: "Secretaría",
			icon: "home",
		},
		{
			label: __("Socio"),
			type: "Link",
			link_type: "DocType",
			link_to: "Socio",
			icon: "user",
		},
		{
			label: __("Valores de Cuota Social"),
			type: "Link",
			link_type: "Page",
			link_to: "valores-cuota-social",
			icon: "wallet",
		},
		{
			label: __("Informes"),
			type: "Section Break",
			icon: "file-text",
			indent: 1,
		},
		{
			label: __("Deuda por equipo"),
			type: "Link",
			link_type: "Report",
			link_to: "Deuda por equipo",
			icon: "table",
			child: 1,
		},
		{
			label: __("Pagos por equipo"),
			type: "Link",
			link_type: "Report",
			link_to: "Pagos por equipo",
			icon: "table",
			child: 1,
		},
	];

	club_management.secretaria_sidebar.ensure_boot = function () {
		if (!club_management.club_desk_navigation?.has_panel_role?.()) {
			return;
		}
		const boot = frappe.boot.workspace_sidebar_item || {};
		frappe.boot.workspace_sidebar_item = boot;
		if (boot[SIDEBAR_KEY]?.items?.length) {
			return;
		}
		boot[SIDEBAR_KEY] = {
			label: __("Secretaría"),
			items: SIDEBAR_ITEMS,
			header_icon: "users",
			module: "Members",
			app: "club_management",
		};
	};

	club_management.secretaria_sidebar.refresh = function () {
		this.ensure_boot();
		if (frappe.app?.sidebar) {
			frappe.app.sidebar.setup(__("Secretaría"));
		}
	};
})();
