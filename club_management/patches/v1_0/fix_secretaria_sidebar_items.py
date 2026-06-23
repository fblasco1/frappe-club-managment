"""Re-sincroniza sidebar Secretaría (fix ítems Section Break + boot)."""

from __future__ import annotations

from club_management.members.setup.secretaria_workspace_sidebar import sync_secretaria_workspace_sidebar


def execute() -> None:
	sync_secretaria_workspace_sidebar()
