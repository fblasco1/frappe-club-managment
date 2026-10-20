// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

frappe.query_reports["Bajas de socios"] = {
	filters: [
		{
			fieldname: "fecha_desde",
			label: __("Desde"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "fecha_hasta",
			label: __("Hasta"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "actividad",
			label: __("Actividad"),
			fieldtype: "Link",
			options: "Actividad",
		},
		{
			fieldname: "tiene_deuda",
			label: __("Deuda pendiente"),
			fieldtype: "Select",
			options: "\nCon deuda\nSin deuda",
		},
	],
	onload(report) {
		club_management.equipo_report?.enhance_page?.(report);
		report.page.set_primary_action(__("Generar reporte"), () => report.refresh());
	},
};
