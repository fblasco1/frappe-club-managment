(function () {
	const layout = club_management.equipo_report.settings;

	function open_a4_portrait_dialog(report, { for_pdf }) {
		const title = for_pdf ? __("PDF Settings") : null;
		const on_submit = (print_settings) => {
			print_settings.orientation = print_settings.orientation || "Portrait";
			if (!print_settings["page-size"]) {
				print_settings["page-size"] = "A4";
			}
			// Usar plantilla HTML del reporte (legible A4), no la grilla con todas las columnas
			print_settings.pick_columns = 0;
			print_settings.columns = null;
			print_settings.print_format = null;
			if (for_pdf) {
				report.pdf_report(print_settings);
			} else {
				report.print_report(print_settings);
			}
		};
		const dialog = frappe.ui.get_print_settings(
			false,
			on_submit,
			report.report_doc.letter_head,
			null,
			true,
			title
		);
		dialog.set_value("orientation", "Portrait");
		report.add_portrait_warning(dialog);
	}

	function patch_print_menu_for_a4_portrait(report) {
		const pdf_labels = new Set([__("PDF"), "PDF"]);
		const print_labels = new Set([__("Print"), "Print", __("Imprimir")]);
		let changed = false;
		(report.menu_items || []).forEach((item) => {
			if (pdf_labels.has(item.label)) {
				item.action = () => open_a4_portrait_dialog(report, { for_pdf: true });
				changed = true;
			} else if (print_labels.has(item.label)) {
				item.action = () => open_a4_portrait_dialog(report, { for_pdf: false });
				changed = true;
			}
		});
		if (!changed) {
			return;
		}
		report.page.clear_menu();
		report.set_menu_items();
	}

	frappe.query_reports["Deuda por actividad"] = {
		filters: [
			{
				fieldname: "fecha_desde",
				label: __("Fecha desde"),
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.month_start(),
			},
			{
				fieldname: "fecha_hasta",
				label: __("Fecha hasta"),
				fieldtype: "Date",
				reqd: 1,
				default: frappe.datetime.get_today(),
			},
			{
				fieldname: "actividad",
				label: __("Actividad"),
				fieldtype: "Link",
				options: "Actividad",
			},
		],
		// Total visible; expandir actividad → grupo → equipo → socio
		initial_depth: 1,
		get_datatable_options: layout.get_datatable_options,
		after_datatable_render: layout.after_datatable_render,
		onload(report) {
			club_management.equipo_report.enhance_page(report);
			patch_print_menu_for_a4_portrait(report);
		},
	};
})();
