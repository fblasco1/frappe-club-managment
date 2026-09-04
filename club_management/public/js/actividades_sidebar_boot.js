/* global frappe */

(function () {
	frappe.provide("club_management.actividades_sidebar");

	const SIDEBAR_KEY = "gestión de actividades";

	const REPORT_META = {
		"Deuda por equipo": {
			report_type: "Script Report",
			ref_doctype: "Inscripcion Actividad",
		},
		"Pagos por equipo": {
			report_type: "Script Report",
			ref_doctype: "Inscripcion Actividad",
		},
	};

	const SIDEBAR_ITEMS = [
		{
			label: __("Gestión de Actividades"),
			type: "Link",
			link_type: "Workspace",
			link_to: "Gestión de Actividades",
			icon: "home",
		},
		{
			label: __("Catálogo de actividades"),
			type: "Link",
			link_type: "Page",
			link_to: "catalogo-actividades",
			icon: "list",
		},
		{
			label: __("Actividad"),
			type: "Link",
			link_type: "DocType",
			link_to: "Actividad",
			icon: "activity",
		},
		{
			label: __("Grupos / tiras"),
			type: "Link",
			link_type: "DocType",
			link_to: "Grupo Actividad",
			icon: "folder",
		},
		{
			label: __("Equipos / categorías"),
			type: "Link",
			link_type: "DocType",
			link_to: "Equipo Actividad",
			icon: "users",
		},
		{
			label: __("Inscripciones"),
			type: "Link",
			link_type: "DocType",
			link_to: "Inscripcion Actividad",
			icon: "edit",
		},
		{
			label: __("Informes"),
			type: "Section Break",
			icon: "file-text",
			indent: 1,
		},
		{
			label: __("Pagos por equipo"),
			type: "Link",
			link_type: "Report",
			link_to: "Pagos por equipo",
			icon: "table",
			child: 1,
		},
		{
			label: __("Deuda por equipo"),
			type: "Link",
			link_type: "Report",
			link_to: "Deuda por equipo",
			icon: "table",
			child: 1,
		},
	];

	function withReportMeta(items) {
		return (items || []).map((item) => {
			if (item.link_type !== "Report" || item.report) {
				return item;
			}
			const meta = REPORT_META[item.link_to];
			return meta ? { ...item, report: meta } : item;
		});
	}

	function mergeSidebarItems(existing, canonical) {
		const base = existing?.length ? existing : canonical;
		const enriched = withReportMeta(base);
		if (!existing?.length) {
			return enriched;
		}
		const labels = new Set(enriched.map((item) => item.label));
		const missing = withReportMeta(canonical).filter((item) => !labels.has(item.label));
		return enriched.concat(missing);
	}

	club_management.actividades_sidebar.ensure_boot = function () {
		if (!club_management.club_desk_navigation?.has_panel_role?.()) {
			return;
		}
		const boot = frappe.boot.workspace_sidebar_item || {};
		frappe.boot.workspace_sidebar_item = boot;
		const existing = boot[SIDEBAR_KEY]?.items;
		const items = mergeSidebarItems(existing, SIDEBAR_ITEMS);
		boot[SIDEBAR_KEY] = {
			label: __("Gestión de Actividades"),
			items,
			header_icon: "activity",
			module: "Activities",
			app: "club_management",
		};
	};

	club_management.actividades_sidebar.refresh = function () {
		this.ensure_boot();
		if (frappe.app?.sidebar) {
			frappe.app.sidebar.setup(__("Gestión de Actividades"));
		}
	};
})();
