// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

const VISTA_RENDICION = "Rendición por concepto";
const VISTA_PAGOS_DIA = "Pagos del día";

function sync_recaudacion_filter_visibility(report) {
	const vista = report.get_filter_value("vista") || VISTA_RENDICION;
	const isPagosDia = vista === VISTA_PAGOS_DIA;
	const rendicionOnly = [
		"fecha_desde",
		"fecha_hasta",
		"periodo_cobro",
		"agrupacion",
		"solo_cuotas_sociales",
	];
	rendicionOnly.forEach((fieldname) => {
		report.toggle_filter_display(fieldname, !isPagosDia);
	});
	report.toggle_filter_display("fecha", isPagosDia);
	report.toggle_filter_display("medio_pago", !isPagosDia);
}

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
			fieldname: "vista",
			label: __("Vista"),
			fieldtype: "Select",
			options: `${VISTA_RENDICION}\n${VISTA_PAGOS_DIA}`,
			default: VISTA_RENDICION,
			on_change() {
				sync_recaudacion_filter_visibility(frappe.query_report);
			},
		},
		{
			fieldname: "fecha",
			label: __("Fecha"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			hidden: 1,
		},
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
		sync_recaudacion_filter_visibility(report);
		report.page.add_inner_button(__("Exportar Excel"), () => {
			export_recaudacion_rendicion(report, "Excel");
		});
		report.page.add_inner_button(__("Exportar PDF"), () => {
			export_recaudacion_rendicion(report, "PDF");
		});
	},
};
