"""Patch: siembra catálogo de espacios físicos del club."""

from __future__ import annotations

from club_management.spaces.seed import ensure_espacios_catalogo


def execute() -> None:
	ensure_espacios_catalogo()
