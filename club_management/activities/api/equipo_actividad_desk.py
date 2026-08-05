"""APIs Desk del formulario Equipo Actividad."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.services.gestion_actividades_panel import (
	resolve_arancel_efectivo_equipo,
)
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


@frappe.whitelist()
def get_arancel_resumen(equipo_actividad: str) -> dict[str, Any]:
	"""Arancel efectivo (cascada) para mostrar en el formulario Equipo."""
	ensure_secretaria_operacion_access()
	if not frappe.has_permission("Equipo Actividad", "read"):
		frappe.throw(frappe._("Sin permiso para leer Equipo Actividad."), frappe.PermissionError)
	return resolve_arancel_efectivo_equipo(equipo_actividad)
