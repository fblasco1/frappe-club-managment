frappe.query_reports["Deuda cuotas sociales"] = {
	filters: [
		{
			fieldname: "periodo_desde",
			label: __("Período desde (MM/AAAA)"),
			fieldtype: "Data",
		},
		{
			fieldname: "periodo_hasta",
			label: __("Período hasta (MM/AAAA)"),
			fieldtype: "Data",
		},
		{
			fieldname: "categoria",
			label: __("Categoría"),
			fieldtype: "Select",
			options: "\nActivo\nMenor\n2° Hermano\n3° Hermano\nAdherente\nJubilado\nVitalicio\nNo Socio",
		},
		{
			fieldname: "estado",
			label: __("Estado"),
			fieldtype: "Select",
			options:
				"\nPendiente de Validación\nPendiente de Pago\nPendiente de Inscripción\nActivo\nMoroso\nSuspendido\nVitalicio\nBaja",
		},
		{
			fieldname: "socio",
			label: __("Socio"),
			fieldtype: "Link",
			options: "Socio",
		},
	],
};
