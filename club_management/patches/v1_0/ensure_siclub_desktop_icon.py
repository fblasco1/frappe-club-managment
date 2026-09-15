"""Asegura ícono Desk App SICLUB + hijos (accesos Secretaría)."""

from __future__ import annotations

from club_management.members.setup.siclub_desktop_icon import ensure_siclub_desktop_icons


def execute() -> None:
	ensure_siclub_desktop_icons()
