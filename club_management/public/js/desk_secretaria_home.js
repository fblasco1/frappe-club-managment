/** Landing Desk Secretaría: no redirigir /desk al panel de socios (3 iconos del club). */
frappe.provide("club_management.desk");

$(document).on("app_ready", function () {
	if (frappe.boot.club_management_desktop_landing) {
		return;
	}

	const ws = frappe.boot.user?.default_workspace;
	if (!ws?.name) {
		return;
	}

	const path = window.location.pathname.replace(/\/$/, "");
	if (path !== "/desk") {
		return;
	}

	const slug = frappe.router.slug(ws.name);
	if (frappe.workspaces && frappe.workspaces[slug]) {
		frappe.set_route(slug);
	}
});
