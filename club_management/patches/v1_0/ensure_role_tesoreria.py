"""Patch: asegura rol Tesoreria."""

from __future__ import annotations

from club_management.finance.permissions import ensure_role_tesoreria_exists


def execute() -> None:
	ensure_role_tesoreria_exists()
