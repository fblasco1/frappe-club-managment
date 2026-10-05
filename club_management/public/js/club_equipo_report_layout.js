/* global frappe */

(function () {
	frappe.provide("club_management.equipo_report");

	club_management.equipo_report.enhance_page = function (report) {
		report?.page?.main?.addClass?.("club-equipo-report-page");
		const nav = club_management.club_desk_navigation;
		nav?.schedule_refresh?.();
		club_management.secretaria_sidebar?.refresh?.();
		setTimeout(() => {
			nav?.refresh?.();
		}, 200);
	};

	club_management.equipo_report.after_table_render = function () {
		const report = frappe.query_report;
		if (!report?.$report?.length) {
			return;
		}
		report.$report.addClass("club-equipo-report-table");
		report.page?.main?.addClass?.("club-equipo-report-page");
	};

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

	club_management.equipo_report.patch_print_menu_for_a4_portrait = function (report) {
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
	};

	club_management.equipo_report.bind_tree_row_toggle = function (datatable) {
		const body = datatable?.bodyScrollable;
		if (!body || body.dataset.clubTreeRowToggle) {
			return;
		}
		body.dataset.clubTreeRowToggle = "1";
		body.addEventListener("click", (event) => {
			// La flecha ya la maneja DataTable; acá solo el resto de la celda.
			if (event.target.closest(".dt-tree-node__toggle")) {
				return;
			}
			const node = event.target.closest(".dt-tree-node");
			if (!node?.querySelector(".dt-tree-node__toggle")) {
				return;
			}
			const cell = node.closest(".dt-cell");
			const row_index = cell?.dataset.rowIndex;
			if (row_index == null) {
				return;
			}
			const rowmanager = frappe.query_report?.datatable?.rowmanager;
			if (!rowmanager) {
				return;
			}
			if (cell.classList.contains("dt-cell--tree-close")) {
				rowmanager.openSingleNode(row_index);
			} else {
				rowmanager.closeSingleNode(row_index);
			}
		});
	};

	club_management.equipo_report.settings = {
		onload(report) {
			club_management.equipo_report.enhance_page(report);
		},
		after_datatable_render() {
			club_management.equipo_report.after_table_render();
		},
		get_datatable_options(options) {
			options.cellHeight = 36;
			return options;
		},
	};
})();
