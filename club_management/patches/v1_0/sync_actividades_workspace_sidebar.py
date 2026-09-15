"""Sincroniza sidebar del workspace Gestión de Actividades y página de catálogo."""

from __future__ import annotations

import frappe
from frappe.modules.import_file import import_file_by_path

from club_management.activities.setup.actividades_workspace_sidebar import (
	catalogo_actividades_page_fixture_path,
	sync_actividades_workspace_sidebar,
)


def execute() -> None:
	if not frappe.db.exists("Page", "catalogo-actividades"):
		import_file_by_path(catalogo_actividades_page_fixture_path(), force=True)
	sync_actividades_workspace_sidebar()
