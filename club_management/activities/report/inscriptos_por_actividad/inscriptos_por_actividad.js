// Copyright (c) 2026, fblasco1 and contributors
// For license information, please see license.txt

frappe.query_reports["Inscriptos por Actividad"] = {
	filters: [
		{
			fieldname: "actividad",
			label: __("Actividad"),
			fieldtype: "Link",
			options: "Actividad",
			reqd: 1,
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
				const actividad = frappe.query_report.get_filter_value("actividad");
				const grupo = frappe.query_report.get_filter_value("grupo_actividad");
				return {
					query: "club_management.activities.services.reporte_inscriptos_actividad.equipo_actividad_query",
					filters: {
						actividad: actividad || "",
						grupo_actividad: grupo || "",
					},
				};
			},
		},
		{
			fieldname: "estado",
			label: __("Estado"),
			fieldtype: "Select",
			options: "\nActiva\nBaja",
			default: "Activa",
		},
	],
	onload(report) {
		report.page.set_primary_action(__("Generar reporte"), () => {
			const actividad = report.get_filter_value("actividad");
			if (!actividad) {
				frappe.msgprint({
					message: __("Seleccioná una actividad para generar el reporte."),
					indicator: "orange",
				});
				return;
			}
			report.refresh();
		});
	},
};
