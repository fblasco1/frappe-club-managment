"""Quita parent_page=Inicio en Secretaría y Gestión de Actividades."""

from __future__ import annotations

from club_management.members.setup.inicio_workspace import retire_inicio_workspace


def execute() -> None:
	retire_inicio_workspace()
