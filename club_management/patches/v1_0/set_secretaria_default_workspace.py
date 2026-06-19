"""Asigna workspace por defecto a usuarios Secretaria en sitios existentes."""

from __future__ import annotations


def execute() -> None:
	from club_management.members.setup.inicio_workspace import (
		set_secretaria_default_workspace,
		set_secretaria_role_home_page,
	)

	set_secretaria_role_home_page()
	set_secretaria_default_workspace(only_if_empty=False)
