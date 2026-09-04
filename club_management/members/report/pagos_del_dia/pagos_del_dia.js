// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

frappe.query_reports["Pagos del dia"] = {
	filters: [
		{
			fieldname: "fecha",
			label: __("Fecha"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
	],
	onload(report) {
		// Redirige al informe unificado (mismo día en Desde/Hasta)
		const fecha = report.get_filter_value("fecha") || frappe.datetime.get_today();
		frappe.set_route("query-report", "Recaudacion por concepto", {
			fecha_desde: fecha,
			fecha_hasta: fecha,
		});
	},
};
