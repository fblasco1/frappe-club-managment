"""Renombra Workspace Secretaría → Socios (name=title para rutas Desk Frappe v16)."""

from __future__ import annotations

import frappe

from club_management.members.setup.secretaria_workspace import WORKSPACE_LABEL, WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace_sidebar import (
	sync_secretaria_workspace_sidebar,
)

_OLD_NAME = "Secretaría"


def execute() -> None:
	if frappe.db.exists("Workspace", _OLD_NAME):
		if frappe.db.exists("Workspace", WORKSPACE_NAME):
			# Estado inconsistente: conservar Socios y retirar el legacy.
			frappe.delete_doc("Workspace", _OLD_NAME, force=True, ignore_permissions=True)
		else:
			frappe.rename_doc("Workspace", _OLD_NAME, WORKSPACE_NAME, force=True)

	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	frappe.db.set_value(
		"Workspace",
		WORKSPACE_NAME,
		{"label": WORKSPACE_LABEL, "title": WORKSPACE_LABEL},
		update_modified=False,
	)

	# Unificar sidebars: Socios es canónico; Secretaría era el nombre legacy.
	if frappe.db.exists("Workspace Sidebar", _OLD_NAME):
		if frappe.db.exists("Workspace Sidebar", WORKSPACE_NAME):
			frappe.delete_doc("Workspace Sidebar", _OLD_NAME, force=True, ignore_permissions=True)
		else:
			frappe.rename_doc("Workspace Sidebar", _OLD_NAME, WORKSPACE_NAME, force=True)

	sync_secretaria_workspace_sidebar()

	# Desktop Icon Socios → sidebar Socios (si existe).
	if frappe.db.exists("Desktop Icon", WORKSPACE_NAME):
		frappe.db.set_value(
			"Desktop Icon",
			WORKSPACE_NAME,
			{"label": WORKSPACE_LABEL, "link_type": "Workspace Sidebar"},
			update_modified=False,
		)

	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Workspace Sidebar")
	frappe.clear_cache(doctype="Desktop Icon")
