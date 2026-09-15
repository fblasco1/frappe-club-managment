"""API Desk — reubicación puntual de entrenamiento."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.permissions import ensure_spaces_write_access
from club_management.spaces.services.excepcion_horario import (
	suspender_horario_dia as suspender_horario_dia_service,
	upsert_excepcion_horario_dia,
)


@frappe.whitelist()
def reubicar_horario_dia(
	fecha: str,
	espacio_origen: str,
	horario_row: str,
	espacio_destino: str,
	hora_desde: str,
	hora_hasta: str,
	motivo: str | None = None,
) -> dict[str, Any]:
	"""Crea/actualiza Excepcion Horario Dia (solo ese día; no toca grilla)."""
	ensure_spaces_write_access()
	if not frappe.has_permission("Excepcion Horario Dia", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	name = upsert_excepcion_horario_dia(
		fecha=fecha,
		espacio_origen=espacio_origen,
		horario_row=horario_row,
		espacio_destino=espacio_destino,
		hora_desde=hora_desde,
		hora_hasta=hora_hasta,
		motivo=motivo,
	)
	return {"name": name}


@frappe.whitelist()
def suspender_horario_dia(
	fecha: str,
	espacio_origen: str,
	horario_row: str,
	motivo: str | None = None,
) -> dict[str, Any]:
	"""Suspende entrenamiento de grilla solo ese día (no toca grilla semanal)."""
	ensure_spaces_write_access()
	if not frappe.has_permission("Excepcion Horario Dia", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	name = suspender_horario_dia_service(
		fecha=fecha,
		espacio_origen=espacio_origen,
		horario_row=horario_row,
		motivo=motivo,
	)
	return {"name": name}
