(function () {
	const layout = club_management.equipo_report.settings;

	frappe.query_reports["Deuda del club por actividad"] = {
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
		],
		get_datatable_options: layout.get_datatable_options,
		after_datatable_render: layout.after_datatable_render,
		onload(report) {
			club_management.equipo_report.enhance_page(report);
		},
	};
})();
