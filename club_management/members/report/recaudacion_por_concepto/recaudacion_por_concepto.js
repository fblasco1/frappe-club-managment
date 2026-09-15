// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

function export_recaudacion_rendicion(report, file_format) {
	const filters = report.get_values ? report.get_values() : report.get_filter_values();
	open_url_post(
		"/api/method/club_management.members.api.cobranza_desk.export_recaudacion_por_concepto",
		{
			filters: JSON.stringify(filters || {}),
			file_format: file_format,
		}
	);
}

frappe.query_reports["Recaudacion por concepto"] = {
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
			fieldname: "periodo_cobro",
			label: __("Período deuda (MM/YYYY)"),
			fieldtype: "Data",
		},
		{
			fieldname: "agrupacion",
			label: __("Tipo"),
			fieldtype: "Select",
			options: "\nCuota\nArancel\nCTO COMP\nFederativa\nOtro",
		},
		{
			fieldname: "solo_cuotas_sociales",
			label: __("Solo cuotas sociales"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "medio_pago",
			label: __("Medio de pago"),
			fieldtype: "Link",
			options: "Mode of Payment",
		},
	],
	onload(report) {
		report.page.add_inner_button(__("Exportar Excel"), () => {
			export_recaudacion_rendicion(report, "Excel");
		});
		report.page.add_inner_button(__("Exportar PDF"), () => {
			export_recaudacion_rendicion(report, "PDF");
		});
	},
};
