frappe.pages["valores-cuota-social"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Valores de Cuota Social"),
		single_column: true,
	});
	club_management.valores_cuota_social_page.init(page);
};

	frappe.pages["valores-cuota-social"].on_page_show = function () {
		club_management.secretaria_sidebar?.refresh?.();
		club_management.club_desk_navigation?.schedule_refresh?.();
	};
