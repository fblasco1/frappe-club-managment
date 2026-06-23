"""Sidebar Secretaría en bootinfo (Secretaria sin módulo Members en allow_modules)."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace_sidebar import SIDEBAR_ITEMS

_PANEL_ROLES = frozenset({"Secretaria", "System Manager"})


def _sidebar_boot_key() -> str:
	return WORKSPACE_NAME.lower()


def build_secretaria_sidebar_boot_items() -> list[dict[str, Any]]:
	"""Ítems de sidebar listos para `bootinfo.workspace_sidebar_item`."""
	items: list[dict[str, Any]] = []
	for row in SIDEBAR_ITEMS:
		link_to = row.get("link_to")
		link_type = row.get("link_type")
		if link_type == "Report" and link_to and not frappe.db.exists("Report", link_to):
			continue
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


def user_has_secretaria_panel_role(bootinfo: dict[str, Any]) -> bool:
	user = bootinfo.get("user") or {}
	if user.get("name") == "Administrator":
		return True
	roles = user.get("roles") or []
	if isinstance(roles, list) and roles and isinstance(roles[0], str):
		return bool(set(roles).intersection(_PANEL_ROLES))
	return bool(
		{r.get("role") for r in roles if isinstance(r, dict)}.intersection(_PANEL_ROLES)
	)


def apply_secretaria_sidebar_to_boot(bootinfo: dict[str, Any]) -> None:
	"""Garantiza ítems de sidebar del workspace Secretaría en Desk."""
	if not user_has_secretaria_panel_role(bootinfo):
		return
	key = _sidebar_boot_key()
	items = build_secretaria_sidebar_boot_items()
	if not items:
		return
	sidebars = bootinfo.setdefault("workspace_sidebar_item", {})
	sidebars[key] = {
		"label": WORKSPACE_NAME,
		"items": items,
		"header_icon": "users",
		"module": "Members",
		"app": "club_management",
	}
