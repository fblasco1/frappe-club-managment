"""Patch: sincroniza workspace Espacios / Gestión de Espacios y Canchas."""

from __future__ import annotations

from pathlib import Path

from frappe.modules.import_file import import_file_by_path

from club_management.patches.v1_0.ensure_spaces_module import execute as ensure_module
from club_management.spaces.permissions import ensure_role_coordinacion_exists
from club_management.spaces.setup.espacios_workspace_sidebar import ensure_espacios_desk_dashboard

_DOCTYPE_FOLDERS = (
	"horario_entrenamiento",
	"espacio",
	"reserva_espacio_dia",
	"reserva_espacio",
)


def _ensure_spaces_doctypes() -> None:
	"""Importa DocTypes Spaces si aún no están en la DB (p. ej. primer migrate)."""
	import frappe

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
	ensure_espacios_desk_dashboard()
