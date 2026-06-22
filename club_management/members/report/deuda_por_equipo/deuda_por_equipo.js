frappe.query_reports["Deuda por equipo"] = {
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
			label: __("Incluir socios sin deuda en rango"),
			fieldtype: "Check",
			default: 0,
		},
	],
	onload(report) {
		report.page.add_inner_button(__("Liquidar rango del socio"), () => {
			const filters = frappe.query_report.get_values();
			frappe.prompt(
				[
					{
						fieldname: "socio",
						label: __("Socio"),
						fieldtype: "Link",
						options: "Socio",
						reqd: 1,
					},
				],
				(values) => {
					frappe.call({
						method:
							"club_management.members.api.liquidacion_equipo_desk.liquidar_deuda_socio_en_rango_desk",
						args: {
							socio: values.socio,
							fecha_desde: filters.fecha_desde,
							fecha_hasta: filters.fecha_hasta,
						},
						freeze: true,
						callback(r) {
							if (!r.exc) {
								frappe.show_alert({
									message: __("Liquidación registrada"),
									indicator: "green",
								});
								frappe.query_report.refresh();
							}
						},
					});
				},
				__("Liquidar deuda en rango"),
				__("Liquidar")
			);
		});
	},
};
