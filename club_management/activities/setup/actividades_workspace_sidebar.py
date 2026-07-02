"""Sidebar Desk del workspace Gestión de Actividades."""

from __future__ import annotations

import frappe

from club_management.members.setup.inicio_workspace import GESTION_ACTIVIDADES_WORKSPACE_NAME

CATALOGO_ACTIVIDADES_PAGE = "catalogo-actividades"

SIDEBAR_ITEMS: list[dict] = [
	{
		"label": "Gestión de Actividades",
		"type": "Link",
		"link_type": "Workspace",
		"link_to": GESTION_ACTIVIDADES_WORKSPACE_NAME,
		"icon": "home",
	},
	{
		"label": "Catálogo de actividades",
		"type": "Link",
		"link_type": "Page",
		"link_to": CATALOGO_ACTIVIDADES_PAGE,
		"icon": "list",
	},
	{
		"label": "Actividad",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Actividad",
		"icon": "activity",
	},
	{
		"label": "Grupos / tiras",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Grupo Actividad",
		"icon": "folder",
	},
	{
		"label": "Equipos / categorías",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Equipo Actividad",
		"icon": "users",
	},
	{
		"label": "Inscripciones",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Inscripcion Actividad",
		"icon": "edit",
	},
	{
		"label": "Informes",
		"type": "Section Break",
		"icon": "file-text",
		"indent": 1,
	},
	{
		"label": "Pagos por equipo",
		"type": "Link",
		"link_type": "Report",
		"link_to": "Pagos por equipo",
		"icon": "table",
		"child": 1,
	},
	{
		"label": "Deuda por equipo",
		"type": "Link",
		"link_type": "Report",
		"link_to": "Deuda por equipo",
		"icon": "table",
		"child": 1,
	},
]


def actividades_sidebar_fixture_path() -> str:
	return frappe.get_app_path(
		"club_management",
		"workspace_sidebar",
		"gestion_actividades.json",
	)


def catalogo_actividades_page_fixture_path() -> str:
	return frappe.get_app_path(
		"club_management",
		"activities",
		"page",
		"catalogo_actividades",
		"catalogo_actividades.json",
	)


def sync_actividades_workspace_sidebar() -> None:
	"""Reemplaza ítems de la sidebar pública del workspace Actividades."""
	if not frappe.db.exists("Workspace", GESTION_ACTIVIDADES_WORKSPACE_NAME):
		return

	if not frappe.db.exists("Workspace Sidebar", GESTION_ACTIVIDADES_WORKSPACE_NAME):
		frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": GESTION_ACTIVIDADES_WORKSPACE_NAME,
				"name": GESTION_ACTIVIDADES_WORKSPACE_NAME,
				"app": "club_management",
				"header_icon": "activity",
				"module": "Activities",
				"standard": 1,
			}
		).insert(ignore_permissions=True)

	rows = []
	for idx, item in enumerate(SIDEBAR_ITEMS, start=1):
		if item.get("link_type") == "Page" and not frappe.db.exists("Page", item["link_to"]):
			continue
		if item.get("link_type") == "Report" and not frappe.db.exists("Report", item["link_to"]):
			continue
		row = {**item, "idx": idx}
		if row.get("type") != "Link":
			row.pop("link_type", None)
			row.pop("link_to", None)
		rows.append(row)

	frappe.db.delete("Workspace Sidebar Item", {"parent": GESTION_ACTIVIDADES_WORKSPACE_NAME})
	for row in rows:
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Sidebar Item",
				"parent": GESTION_ACTIVIDADES_WORKSPACE_NAME,
				"parenttype": "Workspace Sidebar",
				"parentfield": "items",
				**row,
			}
		)
		doc.insert(ignore_permissions=True)

	frappe.db.set_value(
		"Workspace Sidebar",
		GESTION_ACTIVIDADES_WORKSPACE_NAME,
		{
			"app": "club_management",
			"header_icon": "activity",
			"module": "Activities",
			"standard": 1,
		},
		update_modified=False,
	)
	frappe.clear_cache(doctype="Workspace Sidebar")
