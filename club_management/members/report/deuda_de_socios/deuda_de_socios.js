(function () {
	const report_ui = club_management.equipo_report;
	const layout = report_ui.settings;

	function clear_filters(report, fieldnames) {
		fieldnames.forEach((fieldname) => {
			const filter = report.get_filter(fieldname);
			if (filter && filter.get_value()) {
				filter.set_value("");
			}
		});
	}

	frappe.query_reports["Deuda de socios"] = {
		filters: [
			{
				fieldname: "vista",
				label: __("Vista"),
				fieldtype: "Select",
				options: "Por actividad\nLista de socios",
				default: "Por actividad",
				reqd: 1,
			},
			{
				fieldname: "concepto",
				label: __("Concepto"),
				fieldtype: "Select",
				options: "Todo\nSolo cuota social\nSolo arancel",
				default: "Todo",
				reqd: 1,
			},
			{
				fieldname: "periodo_desde",
				label: __("Período desde (MM/AAAA)"),
				fieldtype: "Data",
			},
			{
				fieldname: "periodo_hasta",
				label: __("Período hasta (MM/AAAA)"),
				fieldtype: "Data",
			},
			{
				fieldname: "categoria",
				label: __("Categoría"),
				fieldtype: "Select",
				options: "\nActivo\nMenor\n2° Hermano\n3° Hermano\nAdherente\nJubilado\nVitalicio\nNo Socio",
			},
			{
				fieldname: "estado",
				label: __("Estado"),
				fieldtype: "Select",
				options:
					"\nPendiente de Validación\nPendiente de Pago\nPendiente de Inscripción\nActivo\nMoroso\nSuspendido\nVitalicio\nBaja",
			},
			{
				fieldname: "socio",
				label: __("Socio"),
				fieldtype: "Link",
				options: "Socio",
			},
			{
				fieldname: "actividad",
				label: __("Actividad"),
				fieldtype: "Link",
				options: "Actividad",
				on_change(report) {
					clear_filters(report, ["grupo_actividad", "equipo_actividad"]);
					report.refresh();
				},
			},
			{
				fieldname: "grupo_actividad",
				label: __("Grupo / tira"),
				fieldtype: "Link",
				options: "Grupo Actividad",
				get_query() {
					const actividad = frappe.query_report.get_filter_value("actividad");
					return actividad ? { filters: { actividad } } : {};
				},
				on_change(report) {
					clear_filters(report, ["equipo_actividad"]);
					report.refresh();
				},
			},
			{
				fieldname: "equipo_actividad",
				label: __("Equipo / categoría"),
				fieldtype: "Link",
				options: "Equipo Actividad",
				get_query() {
					const grupo_actividad = frappe.query_report.get_filter_value("grupo_actividad");
					return grupo_actividad ? { filters: { grupo_actividad } } : {};
				},
			},
		],
		// Árbol: Total visible; expandir actividad → grupo → equipo → socio
		initial_depth: 1,
		get_datatable_options: layout.get_datatable_options,
		after_datatable_render(datatable) {
			layout.after_datatable_render();
			report_ui.bind_tree_row_toggle(datatable);
		},
		onload(report) {
			report_ui.enhance_page(report);
			report.page?.main?.addClass?.("club-report-sin-fila-total");
			report_ui.patch_print_menu_for_a4_portrait(report);
		},
	};
})();
