// Spec: club_management/specs/portal_alta_grupo_familiar.md
frappe.ui.form.on("Solicitud Grupo Familiar", {
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}

		frm.add_custom_button(__("Ver solicitudes del trámite"), () => {
			frappe.set_route("List", "Solicitud Asociacion", {
				solicitud_grupo: frm.doc.name,
			});
		});

		if (!frm.doc.grupo_familiar_generado && frm.doc.solicitud_titular) {
			frm.dashboard.set_headline(
				__("Validá primero la solicitud del titular: es la que crea el Grupo Familiar.")
			);
		}
	},
});
