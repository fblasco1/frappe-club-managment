"""Sidebar Desk del workspace Secretaría (fixture + patch)."""

from __future__ import annotations

import frappe

from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME

SIDEBAR_ITEMS: list[dict] = [
	{
		"label": "Secretaría",
		"type": "Link",
		"link_type": "Workspace",
		"link_to": WORKSPACE_NAME,
		"icon": "home",
	},
	{
		"label": "Socio",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Socio",
		"icon": "user",
	},
	{
		"label": "Informes",
		"type": "Section Break",
		"icon": "file-text",
		"indent": 1,
	},
	*[
		{
			"label": report_name,
			"type": "Link",
			"link_type": "Report",
			"link_to": report_name,
			"icon": "table",
			"child": 1,
		}
		for report_name in CLUB_DESK_REPORTS
	],
]

HIDDEN_SIDEBAR_LINKS = frozenset({"Grupo Familiar", "Solicitud Asociacion"})


def secretaria_sidebar_fixture_path() -> str:
	return frappe.get_app_path(
		"club_management",
		"workspace_sidebar",
		"secretaria.json",
	)


def sync_secretaria_workspace_sidebar() -> None:
	"""Reemplaza ítems de la sidebar pública del workspace Secretaría."""
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	if not frappe.db.exists("Workspace Sidebar", WORKSPACE_NAME):
		frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": WORKSPACE_NAME,
				"name": WORKSPACE_NAME,
				"app": "club_management",
				"header_icon": "users",
				"module": "Members",
				"standard": 1,
			}
		).insert(ignore_permissions=True)

	rows = []
	for idx, item in enumerate(SIDEBAR_ITEMS, start=1):
		if item.get("link_type") == "Report" and not frappe.db.exists("Report", item["link_to"]):
			continue
		rows.append({**item, "idx": idx})

	frappe.db.delete("Workspace Sidebar Item", {"parent": WORKSPACE_NAME})
	for row in rows:
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Sidebar Item",
				"parent": WORKSPACE_NAME,
				"parenttype": "Workspace Sidebar",
				"parentfield": "items",
				**row,
			}
		)
		doc.insert(ignore_permissions=True)

	frappe.db.set_value(
		"Workspace Sidebar",
		WORKSPACE_NAME,
		{
			"app": "club_management",
			"header_icon": "users",
			"module": "Members",
			"standard": 1,
		},
		update_modified=False,
	)
	frappe.clear_cache(doctype="Workspace Sidebar")


def remove_secretaria_workspace_report_links() -> None:
	"""Quita informes de los links del workspace (solo sidebar)."""
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	for report_name in CLUB_DESK_REPORTS:
		frappe.db.delete(
			"Workspace Link",
			{
				"parent": WORKSPACE_NAME,
				"parenttype": "Workspace",
				"link_type": "Report",
				"link_to": report_name,
			},
		)
	frappe.clear_cache(doctype="Workspace")
