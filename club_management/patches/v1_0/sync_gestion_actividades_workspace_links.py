"""Sincroniza enlaces jerárquicos del workspace Gestión de Actividades."""

from __future__ import annotations

import frappe
from frappe.modules.import_file import import_file_by_path


def execute() -> None:
	path = frappe.get_app_path(
		"club_management",
		"activities",
		"workspace",
		"gestion_actividades",
		"gestion_actividades.json",
	)
	if not frappe.db.exists("Workspace", "Gestión de Actividades"):
		import_file_by_path(path, force=True)
		return

	import_file_by_path(path, force=True, ignore_version=True)
	frappe.clear_cache(doctype="Workspace")
