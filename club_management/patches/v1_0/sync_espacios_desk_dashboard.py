"""Patch: Page dashboard Espacios + navbar Gestión de Espacios y Canchas + SICLUB."""

from __future__ import annotations

from club_management.members.setup.siclub_desktop_icon import ensure_siclub_desktop_icons
from club_management.spaces.setup.espacios_workspace_sidebar import ensure_espacios_desk_dashboard


def execute() -> None:
	ensure_espacios_desk_dashboard()
	ensure_siclub_desktop_icons()
