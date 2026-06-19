"""Hooks de instalación de `club_management`."""

from __future__ import annotations


def after_install() -> None:
	from club_management.members.setup.inicio_workspace import (
		set_secretaria_default_workspace,
		set_secretaria_role_home_page,
	)

	set_secretaria_role_home_page()
	set_secretaria_default_workspace(only_if_empty=False)
