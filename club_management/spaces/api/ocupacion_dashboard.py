"""API Desk — dashboard de ocupación de espacios."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.permissions import ensure_spaces_read_access
from club_management.spaces.services.ocupacion_dashboard import get_ocupacion_dashboard_payload


@frappe.whitelist()
def get_ocupacion_dashboard(fecha: str | None = None) -> dict[str, Any]:
	"""Planilla de ocupación 08:00–04:00 para la fecha indicada."""
	ensure_spaces_read_access()
	if not frappe.has_permission("Espacio", "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return get_ocupacion_dashboard_payload(fecha=fecha)


@frappe.whitelist()
def get_superposiciones_pendientes() -> list[dict[str, Any]]:
	"""Partidos/fixtures con superposición detectada (Coordinación)."""
	ensure_spaces_read_access()
	if not frappe.has_permission("Reserva Espacio", "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return frappe.get_all(
		"Reserva Espacio",
		filters={"superposicion_detectada": 1, "estado": "Confirmada"},
		fields=[
			"name",
			"espacio",
			"fecha",
			"hora_desde",
			"hora_hasta",
			"motivo",
			"origen_fixture",
			"id_externo_fixture",
		],
		order_by="fecha asc, hora_desde asc",
	)
