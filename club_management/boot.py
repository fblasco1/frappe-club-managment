"""Hooks de arranque (bootinfo) para club_management."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.setup.actividades_sidebar_boot import apply_actividades_sidebar_to_boot
from club_management.members.setup.club_desktop_landing import apply_club_desktop_landing_to_boot
from club_management.members.setup.secretaria_sidebar_boot import apply_secretaria_sidebar_to_boot


def extend_bootinfo(bootinfo: dict[str, Any]) -> None:
	"""Landing Desk de Secretaría, sidebar y workspace por defecto."""
	apply_club_desktop_landing_to_boot(bootinfo)
	apply_secretaria_sidebar_to_boot(bootinfo)
	apply_actividades_sidebar_to_boot(bootinfo)

	user = bootinfo.get("user") or {}
	workspace = user.get("default_workspace")
	if not workspace or not isinstance(workspace, dict):
		return

	name = workspace.get("name")
	if not name or not frappe.db.exists("Workspace", name):
		return

	from club_management.members.setup.club_desktop_landing import user_sees_club_desktop_landing

	if user_sees_club_desktop_landing(user.get("name")):
		return

	from frappe.desk.utils import slug

	path_slug = slug(name)
	is_public = workspace.get("public", True)
	prefix = "/desk/" if is_public else "/desk/private/"
	bootinfo.setdefault("apps_data", {})
	bootinfo["apps_data"]["default_path"] = f"{prefix}{path_slug}"
