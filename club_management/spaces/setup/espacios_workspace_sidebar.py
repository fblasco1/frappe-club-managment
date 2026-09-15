"""Workspace Sidebar y sync del Desk Espacios / Gestión de Espacios y Canchas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.modules.import_file import import_file_by_path

from club_management.spaces.permissions import ensure_role_coordinacion_exists

GESTION_ESPACIOS_WORKSPACE_NAME = "Gestión de Espacios y Canchas"
LEGACY_ESPACIOS_WORKSPACE_NAME = "Espacios"
ESPACIOS_PAGE = "espacios"
OCUPACION_PAGE = "ocupacion-espacios"
WORKSPACE_SEQUENCE_ID = 0.3
SIDEBAR_ESPACIOS = "Espacios"

SIDEBAR_ITEMS: list[dict[str, Any]] = [
	{
		"label": "Inicio Espacios",
		"type": "Link",
		"link_type": "Page",
		"link_to": ESPACIOS_PAGE,
		"icon": "home",
	},
	{
		"label": "Ocupación (planilla)",
		"type": "Link",
		"link_type": "Page",
		"link_to": OCUPACION_PAGE,
		"icon": "calendar",
	},
	{
		"label": "Catálogo de espacios",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Espacio",
		"icon": "organization",
	},
	{
		"label": "Reservas",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Reserva Espacio",
		"icon": "list",
	},
]


def ensure_espacios_page() -> None:
	"""Importa / actualiza la Page dashboard `espacios`."""
	page_json = (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "page"
		/ "espacios"
		/ "espacios.json"
	)
	if page_json.exists():
		import_file_by_path(str(page_json), force=True, ignore_version=True)


def ensure_ocupacion_page() -> None:
	page_json = (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "page"
		/ "ocupacion_espacios"
		/ "ocupacion_espacios.json"
	)
	if page_json.exists():
		import_file_by_path(str(page_json), force=True, ignore_version=True)


def _workspace_fixture_path() -> Path:
	return (
		Path(frappe.get_app_path("club_management"))
		/ "spaces"
		/ "workspace"
		/ "espacios"
		/ "espacios.json"
	)


def sync_gestion_espacios_workspace() -> None:
	"""Crea/actualiza el workspace navbar Gestión de Espacios y Canchas."""
	ensure_role_coordinacion_exists()
	path = _workspace_fixture_path()
	if not path.exists():
		return

	data = json.loads(path.read_text(encoding="utf-8"))
	for key in ("modified", "creation", "modified_by", "owner", "idx"):
		data.pop(key, None)

	name = data.get("name") or GESTION_ESPACIOS_WORKSPACE_NAME
	legacy_exists = bool(frappe.db.exists("Workspace", LEGACY_ESPACIOS_WORKSPACE_NAME))
	target_exists = bool(frappe.db.exists("Workspace", name))

	# Idempotente: si ya existe el workspace nuevo y queda el legacy, borrar legacy.
	# Si solo queda legacy, renombrar. Si ambos, no renombrar (falla por nombre duplicado).
	if legacy_exists and target_exists and LEGACY_ESPACIOS_WORKSPACE_NAME != name:
		frappe.delete_doc(
			"Workspace",
			LEGACY_ESPACIOS_WORKSPACE_NAME,
			force=1,
			ignore_permissions=True,
		)
	elif legacy_exists and not target_exists and name != LEGACY_ESPACIOS_WORKSPACE_NAME:
		frappe.rename_doc(
			"Workspace",
			LEGACY_ESPACIOS_WORKSPACE_NAME,
			name,
			force=True,
			show_alert=False,
		)

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
	data["sequence_id"] = WORKSPACE_SEQUENCE_ID
	data["name"] = name
	data["title"] = GESTION_ESPACIOS_WORKSPACE_NAME
	data["label"] = GESTION_ESPACIOS_WORKSPACE_NAME

	frappe.get_doc(data).insert(ignore_permissions=True)

	if frappe.db.exists("Role", "Coordinacion"):
		frappe.db.set_value(
			"Role",
			"Coordinacion",
			"home_page",
			"/desk/espacios",
			update_modified=False,
		)


def sync_espacios_workspace_sidebar() -> None:
	"""Sidebar usada por SICLUB hijo Espacios y rutas Desk."""
	if not frappe.db.exists("Workspace Sidebar", SIDEBAR_ESPACIOS):
		frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": SIDEBAR_ESPACIOS,
				"name": SIDEBAR_ESPACIOS,
				"app": "club_management",
				"header_icon": "organization",
				"module": "Spaces",
				"standard": 1,
			}
		).insert(ignore_permissions=True)

	frappe.db.delete("Workspace Sidebar Item", {"parent": SIDEBAR_ESPACIOS})
	for idx, item in enumerate(SIDEBAR_ITEMS, start=1):
		if item.get("link_type") == "Page" and not frappe.db.exists("Page", item["link_to"]):
			continue
		row = {**item, "idx": idx}
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Sidebar Item",
				"parent": SIDEBAR_ESPACIOS,
				"parenttype": "Workspace Sidebar",
				"parentfield": "items",
				**row,
			}
		)
		doc.insert(ignore_permissions=True)

	frappe.db.set_value(
		"Workspace Sidebar",
		SIDEBAR_ESPACIOS,
		{
			"app": "club_management",
			"header_icon": "organization",
			"module": "Spaces",
			"standard": 1,
			"title": SIDEBAR_ESPACIOS,
		},
		update_modified=False,
	)
	frappe.clear_cache(doctype="Workspace Sidebar")


def ensure_espacios_desk_dashboard() -> None:
	"""Idempotente: page + workspace navbar + sidebar + home Coordinacion."""
	ensure_role_coordinacion_exists()
	ensure_ocupacion_page()
	ensure_espacios_page()
	sync_gestion_espacios_workspace()
	sync_espacios_workspace_sidebar()
	frappe.clear_cache()
