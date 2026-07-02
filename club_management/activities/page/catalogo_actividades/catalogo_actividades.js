frappe.pages["catalogo-actividades"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Catálogo de actividades"),
		single_column: true,
	});
	club_management.actividades_panel.init_catalog_page(page);
};

frappe.pages["catalogo-actividades"].on_page_show = function () {
	club_management.actividades_sidebar?.refresh?.();
	club_management.club_desk_navigation?.schedule_refresh?.();
	club_management.actividades_panel?.refresh_catalog_page?.();
};
