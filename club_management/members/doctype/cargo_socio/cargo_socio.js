frappe.ui.form.on("Cargo Socio", {
	refresh(frm) {
		const es_secretaria =
			frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager");
		if (!es_secretaria || frm.is_new()) {
			return;
		}
		if (frm.doc.estado === "Pendiente" && frm.doc.modo_cobro === "Unico") {
			frm.add_custom_button(__("Facturar cargo"), () => {
				frappe.call({
					method: "club_management.members.api.cobranza_desk.facturar_cargo_socio",
					args: { cargo: frm.doc.name },
					freeze: true,
					callback(r) {
						if (!r.exc && r.message) {
							frappe.msgprint(
								__("Factura {0} creada", [r.message.sales_invoice])
							);
							frm.reload_doc();
						}
					},
				});
			});
		}
		if (frm.doc.estado === "Pendiente") {
			frm.add_custom_button(__("Cancelar cargo"), () => {
				frappe.confirm(__("¿Cancelar este cargo?"), () => {
					frappe.call({
						method: "club_management.members.api.cobranza_desk.cancelar_cargo_socio",
						args: { cargo: frm.doc.name },
						freeze: true,
						callback(r) {
							if (!r.exc) {
								frappe.show_alert({
									message: __("Cargo cancelado"),
									indicator: "orange",
								});
								frm.reload_doc();
							}
						},
					});
				});
			});
		}
	},
	tipo_cargo(frm) {
		if (!frm.fields_dict.item) {
			return;
		}
		frm.set_query("item", () => {
			const filters = { is_stock_item: 0 };
			if (frm.doc.tipo_cargo === "Cuota Federativa") {
				filters.item_group = ["like", "%FEDERAT%"];
			}
			return { filters };
		});
	},
});
