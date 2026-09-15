"""Jerarquía de workspaces del club (parent_page) para navegación en Desk."""

from __future__ import annotations

import frappe

from club_management.members.setup.inicio_workspace import (
	GESTION_ACTIVIDADES_WORKSPACE_NAME,
	INICIO_WORKSPACE_NAME,
	SECRETARIA_WORKSPACE_NAME,
)


def execute() -> None:
	_links = (
		(SECRETARIA_WORKSPACE_NAME, INICIO_WORKSPACE_NAME),
		(GESTION_ACTIVIDADES_WORKSPACE_NAME, INICIO_WORKSPACE_NAME),
	)
	for workspace_name, parent in _links:
		if frappe.db.exists("Workspace", workspace_name):
			frappe.db.set_value(
				"Workspace",
				workspace_name,
				"parent_page",
				parent,
				update_modified=False,
			)
