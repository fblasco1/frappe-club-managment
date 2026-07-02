"""Sidebar Gestión de Actividades en bootinfo."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.setup.inicio_workspace import GESTION_ACTIVIDADES_WORKSPACE_NAME
from club_management.activities.setup.actividades_workspace_sidebar import SIDEBAR_ITEMS

_PANEL_ROLES = frozenset({"Secretaria", "System Manager"})


def _sidebar_boot_key() -> str:
	return GESTION_ACTIVIDADES_WORKSPACE_NAME.lower()


def build_actividades_sidebar_boot_items() -> list[dict[str, Any]]:
	items: list[dict[str, Any]] = []
	for row in SIDEBAR_ITEMS:
		link_to = row.get("link_to")
		link_type = row.get("link_type")
		if link_type == "Page" and link_to and not frappe.db.exists("Page", link_to):
			continue
		item: dict[str, Any] = {
			"label": frappe._(row["label"]),
			"type": row["type"],
			"icon": row.get("icon", ""),
			"child": row.get("child", 0),
			"collapsible": row.get("collapsible", 1),
			"indent": row.get("indent", 0),
			"keep_closed": row.get("keep_closed", 0),
			"show_arrow": row.get("show_arrow", 0),
		}
		if row["type"] == "Link":
			item["link_to"] = link_to
			item["link_type"] = link_type
		items.append(item)
	return items


def user_has_actividades_panel_role(bootinfo: dict[str, Any]) -> bool:
	user = bootinfo.get("user") or {}
	if user.get("name") == "Administrator":
		return True
	roles = user.get("roles") or []
	if isinstance(roles, list) and roles and isinstance(roles[0], str):
		return bool(set(roles).intersection(_PANEL_ROLES))
	return bool(
		{r.get("role") for r in roles if isinstance(r, dict)}.intersection(_PANEL_ROLES)
	)


def apply_actividades_sidebar_to_boot(bootinfo: dict[str, Any]) -> None:
	if not user_has_actividades_panel_role(bootinfo):
		return
	key = _sidebar_boot_key()
	items = build_actividades_sidebar_boot_items()
	if not items:
		return
	sidebars = bootinfo.setdefault("workspace_sidebar_item", {})
	sidebars[key] = {
		"label": GESTION_ACTIVIDADES_WORKSPACE_NAME,
		"items": items,
		"header_icon": "activity",
		"module": "Activities",
		"app": "club_management",
	}
