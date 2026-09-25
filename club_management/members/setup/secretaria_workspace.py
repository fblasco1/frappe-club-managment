"""Workspace Desk «Socios» (panel operativo; name histórico: Secretaría).

El landing inicial de Secretaría vive en `inicio_workspace.py` (Inicio Club).
En Frappe v16 la ruta Desk usa `title`/`name`: deben coincidir (`Socios` → `/desk/socios`).
"""

from __future__ import annotations

from club_management.members.setup.inicio_workspace import (
	set_secretaria_default_workspace,
	set_secretaria_role_home_page,
)

WORKSPACE_NAME = "Socios"
WORKSPACE_LABEL = "Socios"

__all__ = [
	"WORKSPACE_NAME",
	"WORKSPACE_LABEL",
	"set_secretaria_role_home_page",
	"set_secretaria_default_workspace",
]
