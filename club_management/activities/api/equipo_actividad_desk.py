"""APIs Desk del formulario Equipo Actividad."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.services.inscripcion_actividad_roster import (
	list_socios_inscripcion_grupo_equipo,
)
from club_management.members.services.socio_operaciones_secretaria import ensure_secretaria_operacion_access


@frappe.whitelist()
def list_socios_grupo_equipo(
	grupo_actividad: str | None = None,
	equipo_actividad: str | None = None,
) -> list[dict[str, Any]]:
	ensure_secretaria_operacion_access()
	return list_socios_inscripcion_grupo_equipo(
		grupo_actividad=grupo_actividad,
		equipo_actividad=equipo_actividad,
	)
