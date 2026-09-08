frappe.pages["ocupacion-espacios"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Ocupación de espacios"),
		single_column: true,
	});
	club_management.ocupacion_espacios_page.init(page);
};

frappe.pages["ocupacion-espacios"].on_page_show = function () {
	club_management.club_desk_navigation?.schedule_refresh?.();
	club_management.ocupacion_espacios_page?.refresh?.();
};
