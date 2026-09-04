// Copyright (c) 2026, club_management and contributors
// For license information, please see license.txt

frappe.ui.form.on("Reserva Espacio", {
	refresh(frm) {
		_toggle_alquiler_fields(frm);
	},
	tipo(frm) {
		if (frm.doc.tipo !== "Alquiler externo") {
			frm.set_value("modalidad_alquiler", "");
			frm.set_value("fecha_desde", "");
			frm.set_value("fecha_hasta", "");
			frm.clear_table("dias_recurrencia");
			frm.set_value("arrendatario_nombre", "");
			frm.set_value("arrendatario_contacto", "");
			frm.set_value("item_alquiler", "");
		}
		_toggle_alquiler_fields(frm);
	},
	modalidad_alquiler(frm) {
		_suggest_item_alquiler(frm);
		_toggle_alquiler_fields(frm);
	},
});

frappe.views.calendar["Reserva Espacio"] = {
	field_map: {
		start: "fecha",
		end: "fecha",
		id: "name",
		title: "espacio",
		allDay: true,
	},
	get_events_method: "frappe.desk.calendar.get_events",
	filters: [
		{
			fieldtype: "Link",
			fieldname: "espacio",
			options: "Espacio",
			label: __("Espacio"),
		},
		{
			fieldtype: "Select",
			fieldname: "estado",
			options: "\nBorrador\nConfirmada\nCancelada",
			label: __("Estado"),
		},
	],
};

function _toggle_alquiler_fields(frm) {
	const esAlquiler = frm.doc.tipo === "Alquiler externo";
	const esRec = esAlquiler && frm.doc.modalidad_alquiler === "Recurrente";
	frm.toggle_reqd("modalidad_alquiler", esAlquiler);
	frm.toggle_reqd("arrendatario_nombre", esAlquiler);
	frm.toggle_reqd("fecha", !esRec);
	frm.toggle_reqd("fecha_desde", esRec);
	frm.toggle_reqd("fecha_hasta", esRec);
}

function _suggest_item_alquiler(frm) {
	if (frm.doc.tipo !== "Alquiler externo" || frm.doc.item_alquiler) {
		return;
	}
	const code =
		frm.doc.modalidad_alquiler === "Recurrente"
			? "ICDPE-ALQ-ARS-REC"
			: frm.doc.modalidad_alquiler === "Temporal"
				? "ICDPE-ALQ-ARS-TEMP"
				: null;
	if (!code) {
		return;
	}
	frappe.db.exists("Item", code).then((exists) => {
		if (exists) {
			frm.set_value("item_alquiler", code);
		}
	});
}
