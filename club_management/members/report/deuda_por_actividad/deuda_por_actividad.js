(function () {
	const report_ui = club_management.equipo_report;
	const layout = report_ui.settings;

	frappe.query_reports["Deuda por actividad"] = {
		filters: [
			{
				fieldname: "fecha_desde",
				label: __("Fecha desde"),
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.month_start(),
			},
			{
				fieldname: "fecha_hasta",
				label: __("Fecha hasta"),
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "actividad",
				label: __("Actividad"),
				fieldtype: "Link",
				options: "Actividad",
			},
		],
		// Total visible; expandir actividad → grupo → equipo → socio
		initial_depth: 1,
		get_datatable_options: layout.get_datatable_options,
		after_datatable_render(datatable) {
			layout.after_datatable_render();
			report_ui.bind_tree_row_toggle(datatable);
		},
		onload(report) {
			report_ui.enhance_page(report);
			report_ui.patch_print_menu_for_a4_portrait(report);
		},
	};
})();
