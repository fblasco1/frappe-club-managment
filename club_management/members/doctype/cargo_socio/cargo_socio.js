window.club_management_cargo_extra = window.club_management_cargo_extra || {};

club_management_cargo_extra.aplicar_filtro_conceptos = function (frm) {
	if (!frm.fields_dict.item) {
		return Promise.resolve();
	}
	if (!frm.doc.socio) {
		frm.__conceptos_cargo_extra = null;
		frm.set_query("item", () => ({ filters: { is_stock_item: 0 } }));
		return Promise.resolve();
	}
	return frappe
		.call({
			method: "club_management.members.api.cargo_extra_desk.list_conceptos_cargo_extra",
			args: { socio: frm.doc.socio },
		})
		.then((r) => {
			const conceptos = (r && r.message) || [];
			const codes = conceptos.map((c) => c.item_code);
			frm.__conceptos_cargo_extra = codes;
			frm.set_query("item", () => ({ filters: { name: ["in", codes] } }));
		});
};

frappe.ui.form.on("Cargo Socio", {
	onload(frm) {
		club_management_cargo_extra.aplicar_filtro_conceptos(frm);
	},
	refresh(frm) {
		club_management_cargo_extra.aplicar_filtro_conceptos(frm);

		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__(
					"Los conceptos disponibles corresponden a las actividades del socio más los conceptos generales (multa, etc.). El cargo único se factura al guardar."
				)
			);
			return;
		}

		const es_secretaria =
			frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager");
		if (!es_secretaria) {
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
							frappe.msgprint(__("Factura {0} creada", [r.message.sales_invoice]));
							frm.reload_doc();
						}
					},
				});
			});
		}

		if (frm.doc.estado === "Pendiente" && frm.doc.modo_cobro === "Recurrente") {
			frm.add_custom_button(__("Prepagar / cancelación total"), () => {
				club_management_cargo_extra.dialog_prepago(frm);
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
	socio(frm) {
		frm.set_value("item", null);
		club_management_cargo_extra.aplicar_filtro_conceptos(frm);
	},
});

club_management_cargo_extra.dialog_prepago = function (frm) {
	frappe.call({
		method: "club_management.members.api.cargo_extra_desk.list_meses_prepago",
		args: { cargo: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.exc) return;
			const rows = (r.message || []).filter((row) => !row.ya_facturado);
			if (!rows.length) {
				frappe.msgprint(__("No hay meses pendientes de prepago para este cargo."));
				return;
			}
			const options = rows.map((row) => {
				const monto = frappe.format(row.monto, { fieldtype: "Currency" });
				return {
					label: `${row.periodo} — ${monto}`,
					value: row.periodo,
					checked: true,
				};
			});
			const total = rows.reduce((acc, row) => acc + flt(row.monto), 0);
			const d = new frappe.ui.Dialog({
				title: __("Prepagar / cancelación total"),
				fields: [
					{
						fieldname: "periodos",
						fieldtype: "MultiCheck",
						label: __("Meses a facturar"),
						options: options,
						reqd: 1,
					},
					{
						fieldname: "total_info",
						fieldtype: "HTML",
						options: `<p>${__("Total estimado")}: <b>${frappe.format(total, {
							fieldtype: "Currency",
						})}</b></p>`,
					},
				],
				primary_action_label: __("Facturar meses"),
				primary_action(values) {
					const selected = values.periodos || [];
					if (!selected.length) {
						frappe.msgprint(__("Seleccioná al menos un mes."));
						return;
					}
					d.hide();
					frappe.call({
						method: "club_management.members.api.cargo_extra_desk.prepagar_cargo",
						args: { cargo: frm.doc.name, periodos: selected },
						freeze: true,
						callback(res) {
							if (!res.exc && res.message) {
								const invs = res.message.sales_invoices || [];
								frappe.msgprint(
									__("Facturas creadas: {0}", [invs.join(", ") || __("(ninguna nueva)")])
								);
								frm.reload_doc();
							}
						},
					});
				},
			});
			d.show();
		},
	});
};