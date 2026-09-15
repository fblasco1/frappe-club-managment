// Client script de `Solicitud Asociacion` (Sprint 1 Commit 3).

frappe.ui.form.on("Solicitud Asociacion", {
	refresh(frm) {
		const state = frm.doc.workflow_state;
		if (
			state === "Pendiente" ||
			state === "Requiere Corrección"
		) {
			frm.set_intro(
				__(
					"Para rechazar: complete «Motivos de rechazo», guarde el documento y luego use la acción «Rechazar» del workflow."
				),
				"blue"
			);
		}
	},
});
