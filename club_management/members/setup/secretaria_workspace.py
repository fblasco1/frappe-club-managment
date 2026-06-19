"""Workspace Desk «Secretaría» (panel operativo de socios).

El landing inicial de Secretaría vive en `inicio_workspace.py` (Inicio Club).
"""

from __future__ import annotations

from club_management.members.setup.inicio_workspace import (
	set_secretaria_default_workspace,
	set_secretaria_role_home_page,
)

WORKSPACE_NAME = "Secretaría"
WORKSPACE_LABEL = WORKSPACE_NAME

__all__ = [
	"WORKSPACE_NAME",
	"WORKSPACE_LABEL",
	"set_secretaria_role_home_page",
	"set_secretaria_default_workspace",
]
