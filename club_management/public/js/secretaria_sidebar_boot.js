/* global frappe */

(function () {
	frappe.provide("club_management.secretaria_sidebar");

	const SIDEBAR_KEY = "secretaría";

	const REPORT_META = {
		"Deuda por equipo": {
			report_type: "Script Report",
			ref_doctype: "Inscripcion Actividad",
		},
		"Pagos por equipo": {
			report_type: "Script Report",
			ref_doctype: "Inscripcion Actividad",
		},
		"Recaudacion por concepto": {
			report_type: "Script Report",
			ref_doctype: "Payment Entry",
		},
	};

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
		{
			label: __("Recaudación"),
			type: "Link",
			link_type: "Report",
			link_to: "Recaudacion por concepto",
			icon: "table",
			child: 1,
		},
	];

	function item_key(item) {
		if (item.link_type === "Report" || item.link_type === "DocType" || item.link_type === "Page") {
			return `${item.link_type}:${item.link_to}`;
		}
		return `label:${item.label}`;
	}

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
		const keys = new Set(enriched.map((item) => item_key(item)));
		const legacyReportLinks = new Set([
			"Report:Deuda por actividad",
			"Report:Pagos del dia",
		]);
		const filtered = enriched.filter((item) => !legacyReportLinks.has(item_key(item)));
		const filteredKeys = new Set(filtered.map((item) => item_key(item)));
		const missing = withReportMeta(canonical).filter((item) => !filteredKeys.has(item_key(item)));
		return filtered.concat(missing);
	}

	club_management.secretaria_sidebar.ensure_boot = function () {
		if (!club_management.club_desk_navigation?.has_panel_role?.()) {
			return;
		}
		const boot = frappe.boot.workspace_sidebar_item || {};
		frappe.boot.workspace_sidebar_item = boot;
		const existing = boot[SIDEBAR_KEY]?.items;
		const items = mergeSidebarItems(existing, SIDEBAR_ITEMS);
		boot[SIDEBAR_KEY] = {
			label: __("Secretaría"),
			items,
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
