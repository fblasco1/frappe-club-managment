"""Sincroniza sidebar del workspace Secretaría (Secretaría, Socio, Informes)."""

from __future__ import annotations

from club_management.members.setup.secretaria_workspace_sidebar import (
	remove_secretaria_workspace_report_links,
	sync_secretaria_workspace_sidebar,
)


def execute() -> None:
	remove_secretaria_workspace_report_links()
	sync_secretaria_workspace_sidebar()
