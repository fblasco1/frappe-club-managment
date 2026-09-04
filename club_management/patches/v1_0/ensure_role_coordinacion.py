"""Patch: asegura rol Coordinacion."""

from __future__ import annotations

from club_management.spaces.permissions import ensure_role_coordinacion_exists


def execute() -> None:
	ensure_role_coordinacion_exists()
