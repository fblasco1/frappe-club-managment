// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

frappe.query_reports["Proyeccion Flujo de Fondos"] = {
	filters: [
		{
			fieldname: "as_of_date",
			label: __("Fecha de referencia"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "ventana_dias",
			label: __("Ventana (días)"),
			fieldtype: "Int",
			default: 5,
			reqd: 1,
		},
	],
};
