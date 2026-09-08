"""Patch: página Ocupación de espacios + atajo en workspace Espacios."""

from __future__ import annotations

from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path

from club_management.patches.v1_0.sync_espacios_workspace import execute as sync_espacios_workspace


def execute() -> None:
	page_json = (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "page"
		/ "ocupacion_espacios"
		/ "ocupacion_espacios.json"
	)
	if page_json.exists():
		import_file_by_path(str(page_json), force=True, ignore_version=True)
		# Cliente de la página
		page_js = page_json.with_suffix(".js")
		if page_js.exists():
			# Frappe sincroniza JS vía sync_for; force import del JSON alcanza en migrate
			pass
	frappe.clear_cache()
	sync_espacios_workspace()
