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

club_management_cargo_extra.offer_registrar_cobro = function (socio, sales_invoices, on_done) {
	const invoices = (sales_invoices || []).filter(Boolean);
	if (!socio || !invoices.length) {
		if (on_done) on_done();
		return;
	}
	frappe.confirm(
		__("Cargo facturado. ¿Registrar cobro ahora?"),
		() => club_management_cargo_extra.dialog_cobro_facturas(socio, invoices, on_done),
		() => {
			if (on_done) on_done();
		}
	);
};

club_management_cargo_extra.dialog_cobro_facturas = function (socio, sales_invoices, on_done) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_facturas_pendientes",
		args: { socio },
		freeze: true,
		callback(r) {
			if (r.exc) return;
			const wanted = new Set((sales_invoices || []).filter(Boolean));
			let rows = r.message || [];
			if (wanted.size) {
				rows = rows.filter((row) => wanted.has(row.name));
			}
			if (!rows.length) {
				frappe.msgprint(__("No hay saldo pendiente para cobrar en esas facturas."));
				if (on_done) on_done();
				return;
			}
			const fake_frm = {
				doc: { name: socio },
				reload_doc() {
					if (on_done) on_done();
				},
			};
			if (window.club_management_socio_desk && club_management_socio_desk.prompt_cobro_multi_factura) {
				club_management_socio_desk.prompt_cobro_multi_factura(fake_frm, rows);
				return;
			}
			club_management_cargo_extra.dialog_cobro_simple(socio, rows, on_done);
		},
	});
};

club_management_cargo_extra.dialog_cobro_simple = function (socio, rows, on_done) {
	frappe.call({
		method: "club_management.members.api.cobranza_desk.list_modos_pago_cobranza",
		callback(r) {
			if (r.exc) return;
			const modos = r.message || [];
			const labelToValue = {};
			const mode_options = modos
				.map((row) => {
					labelToValue[row.label] = row.value;
					return row.label;
				})
				.join("\n");
			const total = rows.reduce((acc, row) => acc + flt(row.outstanding_amount), 0);
			const d = new frappe.ui.Dialog({
				title: __("Registrar cobro"),
				fields: [
					{
						fieldname: "mode_1",
						fieldtype: "Select",
						label: __("Medio de pago"),
						options: mode_options,
						default: modos[0]?.label,
						reqd: 1,
					},
					{
						fieldname: "posting_date",
						fieldtype: "Date",
						label: __("Fecha de cobro"),
						default: frappe.datetime.get_today(),
						reqd: 1,
					},
					{
						fieldname: "total_info",
						fieldtype: "HTML",
						options: `<p>${__("Total")}: <b>${frappe.format(total, {
							fieldtype: "Currency",
						})}</b></p>`,
					},
				],
				primary_action_label: __("Confirmar cobro"),
				primary_action(values) {
					d.hide();
					frappe.call({
						method: "club_management.members.api.cobranza_desk.registrar_cobro",
						args: {
							socio,
							sales_invoices: rows.map((row) => row.name),
							mode_of_payment: labelToValue[values.mode_1] || "Cash",
							posting_date: values.posting_date,
						},
						freeze: true,
						callback(res) {
							if (!res.exc) {
								frappe.show_alert({
									message: __("Cobro registrado"),
									indicator: "green",
								});
								if (on_done) on_done();
							}
						},
					});
				},
			});
			d.show();
		},
	});
};

frappe.ui.form.on("Cargo Socio", {
	onload(frm) {
		club_management_cargo_extra.aplicar_filtro_conceptos(frm);
	},
	refresh(frm) {
		club_management_cargo_extra.aplicar_filtro_conceptos(frm);

		if (frm.is_new()) {
			frm._cargo_era_nuevo = true;
			frm.dashboard.set_headline(
				__(
					"El cargo único se factura al guardar y queda listo para cobrar. El recurrente puede facturar el mes corriente para cobrarlo ya."
				)
			);
			return;
		}

		const es_secretaria =
			frappe.user.has_role("Secretaria") || frappe.user.has_role("System Manager");
		if (!es_secretaria) {
			return;
		}

		if (frm.doc.estado === "Facturado" && frm.doc.sales_invoice) {
			frm.dashboard.set_headline(
				__("Facturado. Para cobrarlo usá «Registrar cobro» (factura {0}).", [
					frm.doc.sales_invoice,
				])
			);
			frm.add_custom_button(__("Registrar cobro"), () => {
				club_management_cargo_extra.dialog_cobro_facturas(
					frm.doc.socio,
					[frm.doc.sales_invoice],
					() => frm.reload_doc()
				);
			});
		}

		if (frm.doc.estado === "Pendiente" && frm.doc.modo_cobro === "Unico") {
			frm.add_custom_button(__("Facturar cargo"), () => {
				frappe.call({
					method: "club_management.members.api.cobranza_desk.facturar_cargo_socio",
					args: { cargo: frm.doc.name },
					freeze: true,
					callback(r) {
						if (!r.exc && r.message) {
							frm.reload_doc();
							club_management_cargo_extra.offer_registrar_cobro(
								frm.doc.socio,
								[r.message.sales_invoice],
								() => frm.reload_doc()
							);
						}
					},
				});
			});
		}

		if (frm.doc.estado === "Pendiente" && frm.doc.modo_cobro === "Recurrente") {
			frm.add_custom_button(__("Facturar mes corriente"), () => {
				frappe.call({
					method: "club_management.members.api.cargo_extra_desk.facturar_mes_corriente",
					args: { cargo: frm.doc.name },
					freeze: true,
					callback(r) {
						if (!r.exc && r.message) {
							const invs = r.message.sales_invoices || [];
							if (!invs.length) {
								frappe.msgprint(__("El mes corriente ya estaba facturado."));
								frm.reload_doc();
								return;
							}
							frm.reload_doc();
							club_management_cargo_extra.offer_registrar_cobro(
								frm.doc.socio,
								invs,
								() => frm.reload_doc()
							);
						}
					},
				});
			});
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
	after_save(frm) {
		if (!frm._cargo_era_nuevo) {
			return;
		}
		frm._cargo_era_nuevo = false;
		if (frm.doc.estado === "Facturado" && frm.doc.sales_invoice) {
			club_management_cargo_extra.offer_registrar_cobro(
				frm.doc.socio,
				[frm.doc.sales_invoice],
				() => frm.reload_doc()
			);
		} else if (frm.doc.estado === "Pendiente" && frm.doc.modo_cobro === "Recurrente") {
			frappe.msgprint({
				title: __("Cargo recurrente creado"),
				message: __(
					"Quedó pendiente para meses futuros. Usá «Facturar mes corriente» para cobrar este mes ahora, o «Generar cargo» en la ficha del socio."
				),
				indicator: "blue",
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
								frm.reload_doc();
								club_management_cargo_extra.offer_registrar_cobro(
									frm.doc.socio,
									invs,
									() => frm.reload_doc()
								);
							}
						},
					});
				},
			});
			d.show();
		},
	});
};
