"""Patch: sincroniza workspace Espacios."""

from __future__ import annotations

import json
import os
from pathlib import Path

import frappe
from frappe.modules.import_file import import_file_by_path

from club_management.patches.v1_0.ensure_spaces_module import execute as ensure_module
from club_management.spaces.permissions import ensure_role_coordinacion_exists

WORKSPACE_NAME = "Espacios"
_DOCTYPE_FOLDERS = (
	"horario_entrenamiento",
	"espacio",
	"reserva_espacio_dia",
	"reserva_espacio",
)


def _ensure_spaces_doctypes() -> None:
	"""Importa DocTypes Spaces si aún no están en la DB (p. ej. primer migrate)."""
	base = Path(frappe.get_app_path("club_management")) / "spaces" / "doctype"
	for folder in _DOCTYPE_FOLDERS:
		path = base / folder / f"{folder}.json"
		if not path.exists():
			continue
		import_file_by_path(str(path), force=True, ignore_version=True)
	frappe.clear_cache()


def execute() -> None:
	ensure_module()
	ensure_role_coordinacion_exists()
	_ensure_spaces_doctypes()

	path = (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "workspace"
		/ "espacios"
		/ "espacios.json"
	)
	if not path.exists():
		return
	data = json.loads(path.read_text(encoding="utf-8"))
	for key in ("modified", "creation", "modified_by", "owner", "idx"):
		data.pop(key, None)

	name = data.get("name") or WORKSPACE_NAME
	if frappe.db.exists("Workspace", name):
		frappe.delete_doc("Workspace", name, force=1, ignore_permissions=True)

	links = []
	for link in data.get("links") or []:
		row = dict(link)
		row.setdefault("type", "Link")
		links.append(row)
	data["links"] = links

	shortcuts = []
	for sc in data.get("shortcuts") or []:
		row = dict(sc)
		if "type" not in row:
			row["type"] = "DocType"
		shortcuts.append(row)
	data["shortcuts"] = shortcuts

	frappe.get_doc(data).insert(ignore_permissions=True)

	if frappe.db.exists("Role", "Coordinacion"):
		frappe.db.set_value(
			"Role",
			"Coordinacion",
			"home_page",
			"/desk/espacios",
			update_modified=False,
		)
