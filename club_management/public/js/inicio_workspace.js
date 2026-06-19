/** Estilos y navegación del workspace Inicio. */
frappe.provide("club_management.inicio_workspace");

club_management.inicio_workspace.is_inicio = function () {
	const page = frappe.workspace?.page;
	return (
		page?.name === "Inicio" ||
		frappe.router?.slug?.() === "inicio" ||
		frappe.router?.slug?.() === "inicio-club"
	);
};

club_management.inicio_workspace.decorate = function () {
	if (!club_management.inicio_workspace.is_inicio()) {
		$(".layout-main-section").removeClass("club-inicio-workspace");
		return;
	}
	$(".layout-main-section").addClass("club-inicio-workspace");
};

$(document).on("page-change", function () {
	club_management.inicio_workspace.decorate();
});

frappe.router.on("change", () => {
	setTimeout(() => club_management.inicio_workspace.decorate(), 50);
});
