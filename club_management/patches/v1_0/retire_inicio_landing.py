"""Oculta Inicio y fija Secretaría como landing de Desk."""

from __future__ import annotations

from club_management.members.setup.inicio_workspace import (
	retire_inicio_workspace,
	set_secretaria_default_workspace,
	set_secretaria_role_home_page,
)


def execute() -> None:
	retire_inicio_workspace()
	set_secretaria_role_home_page()
	set_secretaria_default_workspace(only_if_empty=False)
