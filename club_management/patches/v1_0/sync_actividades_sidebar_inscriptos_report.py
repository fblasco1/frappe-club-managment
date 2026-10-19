"""Agrega «Inscriptos por Actividad» a la sidebar de Gestión de Actividades."""

from __future__ import annotations

from club_management.activities.setup.actividades_workspace_sidebar import (
	sync_actividades_workspace_sidebar,
)


def execute() -> None:
	sync_actividades_workspace_sidebar()
