"""Landing Desk de Coordinación: solo ícono Espacios."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.permissions import ROLE_COORDINACION
from club_management.spaces.setup.espacios_workspace_sidebar import SIDEBAR_ESPACIOS

COORDINACION_LANDING_ROLES = frozenset({ROLE_COORDINACION})
_EXCLUDED_FROM_FILTERED_LANDING = frozenset({"System Manager", "Secretaria", "Administrator"})

ESPACIOS_DESK_LANDING_ICONS: tuple[dict[str, Any], ...] = (
	{
		"name": "club-landing-espacios",
		"label": SIDEBAR_ESPACIOS,
		"icon": "organization",
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": SIDEBAR_ESPACIOS,
		"bg_color": "blue",
		"app": "club_management",
		"idx": 1,
		"standard": 0,
		"hidden": 0,
		"parent_icon": None,
		"restrict_removal": 1,
	},
)


def user_sees_espacios_desktop_landing(user: str | None = None) -> bool:
	"""True si el escritorio debe mostrar solo Espacios (rol Coordinacion puro)."""
	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return False
	roles = set(frappe.get_roles(user))
	if roles.intersection(_EXCLUDED_FROM_FILTERED_LANDING):
		return False
	return bool(roles.intersection(COORDINACION_LANDING_ROLES))


def espacios_desktop_landing_icons() -> list[dict[str, Any]]:
	return [dict(icon) for icon in ESPACIOS_DESK_LANDING_ICONS]


def apply_espacios_desktop_landing_to_boot(bootinfo: dict[str, Any]) -> None:
	"""Reemplaza iconos Framework/ERPNext por el landing de Espacios."""
	user_name = (bootinfo.get("user") or {}).get("name") or frappe.session.user
	if not user_sees_espacios_desktop_landing(user_name):
		return

	bootinfo["desktop_icons"] = espacios_desktop_landing_icons()
	bootinfo["club_management_espacios_desktop_landing"] = True

	apps_data = bootinfo.setdefault("apps_data", {})
	if not apps_data.get("default_path") or apps_data.get("default_path") == "/desk":
		apps_data["default_path"] = "/desk"


def apply_espacios_desktop_landing_sidebar_alias(bootinfo: dict[str, Any]) -> None:
	"""Garantiza clave `espacios` en workspace_sidebar_item para el ícono Desktop."""
	user_name = (bootinfo.get("user") or {}).get("name") or frappe.session.user
	if not user_sees_espacios_desktop_landing(user_name):
		return

	sidebars = bootinfo.setdefault("workspace_sidebar_item", {})
	key = SIDEBAR_ESPACIOS.lower()
	if key in sidebars and sidebars[key].get("items"):
		return

	from club_management.spaces.setup.espacios_sidebar_boot import build_espacios_sidebar_boot_items

	items = build_espacios_sidebar_boot_items()
	if not items:
		return
	sidebars[key] = {
		"label": SIDEBAR_ESPACIOS,
		"items": items,
		"header_icon": "organization",
		"module": "Spaces",
		"app": "club_management",
	}
