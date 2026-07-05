frappe.ui.form.on("Beca Socio", {
	onload(frm) {
		if (frm.is_new() && frappe.route_options?.socio && !frm.doc.socio) {
			frm.set_value("socio", frappe.route_options.socio);
		}
	},
	tipo_beca(frm) {
		const tipo = frm.doc.tipo_beca;
		if (tipo === "Total") {
			frm.set_value({ pct_cuota_social: 100, pct_arancel: 100 });
		} else if (tipo === "Parcial Exime Cuota") {
			frm.set_value({ pct_cuota_social: 100, pct_arancel: 0 });
		} else if (tipo === "Parcial Exime Arancel") {
			frm.set_value({ pct_cuota_social: 0, pct_arancel: 100 });
		}
		frm.toggle_enable("pct_cuota_social", tipo === "Parcial Porcentaje");
		frm.toggle_enable("pct_arancel", tipo === "Parcial Porcentaje");
	},
	refresh(frm) {
		frm.trigger("tipo_beca");
		if (frm.is_new()) {
			frm.dashboard.set_headline(
				__(
					"La beca vigente impacta la facturación mensual (cuota social y aranceles). Por defecto la vigencia es de 6 meses."
				)
			);
		}
	},
});
