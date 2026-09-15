(function () {
	const layout = club_management.equipo_report.settings;

	frappe.query_reports["Pagos por equipo"] = {
		filters: [
			{
				fieldname: "actividad",
				label: __("Actividad"),
				fieldtype: "Link",
				options: "Actividad",
				get_query: () => ({ filters: { habilitada: 1 } }),
				on_change: () => {
					frappe.query_report.set_filter_value("grupo_actividad", "");
					frappe.query_report.set_filter_value("equipo_actividad", "");
				},
			},
			{
				fieldname: "grupo_actividad",
				label: __("Grupo / tira"),
				fieldtype: "Link",
				options: "Grupo Actividad",
				get_query: () => {
					const actividad = frappe.query_report.get_filter_value("actividad");
					const filters = { habilitada: 1 };
					if (actividad) {
						filters.actividad = actividad;
					}
					return { filters };
				},
				on_change: () => {
					frappe.query_report.set_filter_value("equipo_actividad", "");
				},
			},
			{
				fieldname: "equipo_actividad",
				label: __("Equipo / categoría"),
				fieldtype: "Link",
				options: "Equipo Actividad",
				get_query: () => {
					const grupo = frappe.query_report.get_filter_value("grupo_actividad");
					const filters = { habilitada: 1 };
					if (grupo) {
						filters.grupo_actividad = grupo;
					}
					return { filters };
				},
				on_change: () => {
					frappe.query_report.set_filter_value("equipos_actividad", "");
				},
			},
			{
				fieldname: "equipos_actividad",
				label: __("Varios equipos / categorías"),
				fieldtype: "MultiSelectList",
				options: "Equipo Actividad",
				get_data(txt) {
					const grupo = frappe.query_report.get_filter_value("grupo_actividad");
					const filters = { habilitada: 1 };
					if (grupo) {
						filters.grupo_actividad = grupo;
					}
					return frappe.db.get_link_options("Equipo Actividad", txt, filters);
				},
				on_change: () => {
					frappe.query_report.set_filter_value("equipo_actividad", "");
				},
			},
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
				fieldname: "incluir_saldo_cero",
				label: __("Incluir socios sin pagos en rango"),
				fieldtype: "Check",
				default: 0,
			},
		],
		get_datatable_options: layout.get_datatable_options,
		after_datatable_render: layout.after_datatable_render,
		onload(report) {
			club_management.equipo_report.enhance_page(report);
			report.page.add_inner_message(
				__(
					"Muestra el arancel cobrado por socio según el ítem del equipo/grupo/actividad. La liquidación del entrenador usa el % configurado en el equipo, grupo o Club Settings. Puede elegir varios equipos para ver el total del entrenador."
				)
			);
		},
	};
})();
