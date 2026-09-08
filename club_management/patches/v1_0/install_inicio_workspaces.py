"""Sincroniza workspaces Inicio Club + Gestión de Actividades y defaults."""

from __future__ import annotations

from club_management.members.setup.inicio_workspace import (
	migrate_legacy_inicio_workspace,
	set_secretaria_default_workspace,
	set_secretaria_role_home_page,
)


def execute() -> None:
	migrate_legacy_inicio_workspace()
	set_secretaria_role_home_page()
	set_secretaria_default_workspace(only_if_empty=False)
