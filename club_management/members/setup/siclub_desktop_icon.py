"""Ícono Desk App SICLUB (modal tipo Framework) con accesos de Secretaría.

Spec: `club_management/specs/siclub_desktop_app.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

from club_management.activities.setup.actividades_workspace_sidebar import (
	SIDEBAR_ITEMS as ACTIVIDADES_SIDEBAR_ITEMS,
)
from club_management.members.setup.inicio_workspace import GESTION_ACTIVIDADES_WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME as SECRETARIA_WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace_sidebar import (
	SIDEBAR_ITEMS as SECRETARIA_SIDEBAR_ITEMS,
)

SICLUB_APP_LABEL = "SICLUB"
SICLUB_APP_NAME = "club_management"
SICLUB_DESK_ROUTE = "/desk/secretaria"
SICLUB_LOGO_URL = "/assets/frappe/images/frappe-framework-logo.svg"

SIDEBAR_SOCIOS = "Socios"
SIDEBAR_ACTIVIDADES = "Actividades"
SIDEBAR_CONFIG = "Configuración de Sistema"

CONFIG_SIDEBAR_ITEMS: list[dict[str, Any]] = [
	{
		"label": "Club Settings",
		"type": "Link",
		"link_type": "DocType",
		"link_to": "Club Settings",
		"icon": "setting",
	},
]

SICLUB_CHILD_ICONS: tuple[dict[str, Any], ...] = (
	{
		"label": SIDEBAR_SOCIOS,
		"icon": "users",
		"link_to": SIDEBAR_SOCIOS,
		"bg_color": "blue",
		"idx": 1,
	},
	{
		"label": SIDEBAR_ACTIVIDADES,
		"icon": "activity",
		"link_to": SIDEBAR_ACTIVIDADES,
		"bg_color": "blue",
		"idx": 2,
	},
	{
		"label": SIDEBAR_CONFIG,
		"icon": "setting",
		"link_to": SIDEBAR_CONFIG,
		"bg_color": "gray",
		"idx": 3,
	},
)


def ensure_siclub_desktop_icons() -> None:
	"""Crea/actualiza App SICLUB + sidebars hijas + Desktop Icons hijos."""
	_ensure_landing_sidebars()
	_ensure_app_icon()
	for child in SICLUB_CHILD_ICONS:
		_ensure_child_icon(child)
	clear_desktop_icons_cache()
	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


def _ensure_landing_sidebars() -> None:
	_upsert_workspace_sidebar(
		SIDEBAR_SOCIOS,
		header_icon="users",
		module="Members",
		items=SECRETARIA_SIDEBAR_ITEMS,
	)
	_upsert_workspace_sidebar(
		SIDEBAR_ACTIVIDADES,
		header_icon="activity",
		module="Activities",
		items=ACTIVIDADES_SIDEBAR_ITEMS,
	)
	_upsert_workspace_sidebar(
		SIDEBAR_CONFIG,
		header_icon="setting",
		module="Members",
		items=CONFIG_SIDEBAR_ITEMS,
	)


def _upsert_workspace_sidebar(
	name: str,
	*,
	header_icon: str,
	module: str,
	items: list[dict[str, Any]],
) -> None:
	exists = frappe.db.exists("Workspace Sidebar", name)
	if exists:
		doc = frappe.get_doc("Workspace Sidebar", name)
		doc.title = name
		doc.header_icon = header_icon
		doc.module = module
		doc.app = SICLUB_APP_NAME
		doc.standard = 1
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": name,
				"header_icon": header_icon,
				"module": module,
				"app": SICLUB_APP_NAME,
				"standard": 1,
			}
		)

	doc.set("items", [])
	for idx, row in enumerate(items, start=1):
		payload = {
			"doctype": "Workspace Sidebar Item",
			"idx": idx,
			"label": row["label"],
			"type": row.get("type", "Link"),
			"icon": row.get("icon"),
			"child": row.get("child", 0),
			"collapsible": row.get("collapsible", 1),
			"indent": row.get("indent", 0),
			"keep_closed": row.get("keep_closed", 0),
			"show_arrow": row.get("show_arrow", 0),
		}
		if row.get("type", "Link") == "Link":
			payload["link_type"] = row.get("link_type")
			payload["link_to"] = row.get("link_to")
		doc.append("items", payload)

	if exists:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)
		# autoname = field:title → name == title
		if doc.name != name:
			frappe.rename_doc("Workspace Sidebar", doc.name, name, force=True, show_alert=False)


def _ensure_app_icon() -> None:
	filters = {"label": SICLUB_APP_LABEL, "icon_type": "App"}
	existing = frappe.db.exists("Desktop Icon", filters)
	if existing:
		doc = frappe.get_doc("Desktop Icon", existing)
	else:
		doc = frappe.new_doc("Desktop Icon")
		doc.label = SICLUB_APP_LABEL
		doc.icon_type = "App"

	doc.link_type = "External"
	doc.link = SICLUB_DESK_ROUTE
	doc.app = SICLUB_APP_NAME
	doc.logo_url = SICLUB_LOGO_URL
	doc.standard = 1
	doc.hidden = 0
	doc.restrict_removal = 1
	doc.idx = 0
	doc.parent_icon = None
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)


def _ensure_child_icon(spec: dict[str, Any]) -> None:
	filters = {"label": spec["label"], "icon_type": "Link", "parent_icon": SICLUB_APP_LABEL}
	existing = frappe.db.exists("Desktop Icon", filters)
	if not existing:
		existing = frappe.db.exists("Desktop Icon", {"label": spec["label"], "icon_type": "Link"})
	if existing:
		doc = frappe.get_doc("Desktop Icon", existing)
	else:
		doc = frappe.new_doc("Desktop Icon")
		doc.label = spec["label"]
		doc.icon_type = "Link"

	doc.link_type = "Workspace Sidebar"
	doc.link_to = spec["link_to"]
	doc.parent_icon = SICLUB_APP_LABEL
	doc.icon = spec["icon"]
	doc.bg_color = spec.get("bg_color") or "blue"
	doc.app = SICLUB_APP_NAME
	doc.standard = 1
	doc.hidden = 0
	doc.restrict_removal = 1
	doc.idx = int(spec.get("idx") or 0)
	if existing:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)


def siclub_child_labels() -> list[str]:
	return [row["label"] for row in SICLUB_CHILD_ICONS]


# Referencias usadas por tests / documentación.
_ = (SECRETARIA_WORKSPACE_NAME, GESTION_ACTIVIDADES_WORKSPACE_NAME)
