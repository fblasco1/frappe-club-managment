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
