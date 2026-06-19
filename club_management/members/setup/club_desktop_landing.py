"""Landing Desk de Secretaría: Socios, Actividades, Configuración de Sistema."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.desk.utils import slug

SECRETARIA_LANDING_ROLES = frozenset({"Secretaria"})

CLUB_DESK_LANDING_ICONS: tuple[dict[str, Any], ...] = (
	{
		"name": "club-landing-socios",
		"label": "Socios",
		"icon": "users",
		"icon_type": "Link",
		"link_type": "External",
		"link": f"/desk/{slug('Secretaría')}",
		"bg_color": "blue",
		"app": "club_management",
		"idx": 1,
		"standard": 0,
		"hidden": 0,
		"parent_icon": None,
		"restrict_removal": 1,
	},
	{
		"name": "club-landing-actividades",
		"label": "Actividades",
		"icon": "activity",
		"icon_type": "Link",
		"link_type": "External",
		"link": f"/desk/{slug('Gestión de Actividades')}",
		"bg_color": "blue",
		"app": "club_management",
		"idx": 2,
		"standard": 0,
		"hidden": 0,
		"parent_icon": None,
		"restrict_removal": 1,
	},
	{
		"name": "club-landing-config",
		"label": "Configuración de Sistema",
		"icon": "setting",
		"icon_type": "Link",
		"link_type": "External",
		"link": f"/desk/{slug('Club Settings')}",
		"bg_color": "gray",
		"app": "club_management",
		"idx": 3,
		"standard": 0,
		"hidden": 0,
		"parent_icon": None,
		"restrict_removal": 1,
	},
)


def user_sees_club_desktop_landing(user: str | None = None) -> bool:
	"""True si el usuario debe ver solo el landing del club (rol Secretaría)."""
	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return False
	return SECRETARIA_LANDING_ROLES.intersection(set(frappe.get_roles(user)))


def club_desktop_landing_icons() -> list[dict[str, Any]]:
	"""Iconos sintéticos para el escritorio inicial de Secretaría."""
	return [dict(icon) for icon in CLUB_DESK_LANDING_ICONS]


def apply_club_desktop_landing_to_boot(bootinfo: dict[str, Any]) -> None:
	"""Reemplaza iconos de Framework/ERPNext por el landing del club."""
	user_name = (bootinfo.get("user") or {}).get("name") or frappe.session.user
	if not user_sees_club_desktop_landing(user_name):
		return

	bootinfo["desktop_icons"] = club_desktop_landing_icons()
	bootinfo["club_management_desktop_landing"] = True

	# Tras sessions.py, apps_data.default_path suele ser /desk (varias apps).
	apps_data = bootinfo.setdefault("apps_data", {})
	if not apps_data.get("default_path") or apps_data.get("default_path") == "/desk":
		apps_data["default_path"] = "/desk"
