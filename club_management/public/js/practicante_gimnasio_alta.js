/* global frappe */
frappe.provide("club_management_practicante_gimnasio");

club_management_practicante_gimnasio.open = function () {
	const d = new frappe.ui.Dialog({
		title: __("Alta practicante gimnasio (No Socio)"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${frappe.utils.escape_html(
					__(
						"Se registra con número NS (sin número de socio), sin cuota social, y queda inscripto en Gimnasio Fitness con el arancel No Socio."
					)
				)}</p>`,
			},
			{ fieldtype: "Section Break", label: __("Datos personales") },
			{ fieldname: "nombre", fieldtype: "Data", label: __("Nombre"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "apellido", fieldtype: "Data", label: __("Apellido"), reqd: 1 },
			{ fieldtype: "Section Break" },
			{ fieldname: "dni", fieldtype: "Data", label: __("DNI"), reqd: 1 },
			{ fieldtype: "Column Break" },
			{
				fieldname: "nacionalidad",
				fieldtype: "Link",
				label: __("Nacionalidad"),
				options: "Country",
				reqd: 1,
				default: "Argentina",
			},
			{ fieldtype: "Column Break" },
			{ fieldname: "fecha_nacimiento", fieldtype: "Date", label: __("Fecha de nacimiento"), reqd: 1 },
			{ fieldtype: "Section Break" },
			{
				fieldname: "genero",
				fieldtype: "Select",
				label: __("Género"),
				options: "\nMasculino\nFemenino\nOtro\nPrefiero no decir",
				reqd: 1,
			},
			{ fieldtype: "Column Break" },
			{ fieldname: "email", fieldtype: "Data", label: __("Email"), options: "Email", reqd: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "telefono_movil", fieldtype: "Data", label: __("Teléfono móvil"), reqd: 1 },
		],
		primary_action_label: __("Registrar"),
		primary_action(values) {
			frappe.call({
				method: "club_management.members.api.gimnasio_desk.crear_practicante_no_socio_desk",
				args: { datos: values },
				freeze: true,
				callback(r) {
					if (r.exc || !r.message || !r.message.socio) {
						return;
					}
					d.hide();
					frappe.set_route("Form", "Socio", r.message.socio);
				},
			});
		},
	});
	d.show();
};
