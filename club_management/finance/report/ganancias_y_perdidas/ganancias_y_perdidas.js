// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

frappe.query_reports["Ganancias y Perdidas"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "period_start_date",
			label: __("Desde"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "period_end_date",
			label: __("Hasta"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "cost_center",
			label: __("Centro de costo"),
			fieldtype: "Link",
			options: "Cost Center",
		},
		{
			fieldname: "periodicity",
			label: __("Periodicidad"),
			fieldtype: "Select",
			options: "Monthly\nQuarterly\nHalf-Yearly\nYearly",
			default: "Monthly",
		},
	],
};
