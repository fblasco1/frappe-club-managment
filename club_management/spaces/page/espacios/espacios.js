frappe.pages["espacios"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Gestión de Espacios y Canchas"),
		single_column: true,
	});
	club_management.espacios_dashboard_page.init(page);
};

frappe.pages["espacios"].on_page_show = function () {
	club_management.club_desk_navigation?.schedule_refresh?.();
	club_management.espacios_sidebar?.schedule_refresh?.();
	club_management.espacios_dashboard_page?.refresh?.();
};
