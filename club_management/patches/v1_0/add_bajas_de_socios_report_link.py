"""Agrega «Bajas de socios» a las sidebars de Socios y Actividades."""

from __future__ import annotations

from club_management.activities.setup.actividades_workspace_sidebar import (
	sync_actividades_workspace_sidebar,
)
from club_management.members.setup.secretaria_workspace_sidebar import (
	sync_secretaria_workspace_sidebar,
)


def execute() -> None:
	sync_secretaria_workspace_sidebar()
	sync_actividades_workspace_sidebar()
