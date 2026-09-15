"""API Desk — suspensión puntual de reserva."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.permissions import ensure_spaces_write_access
from club_management.spaces.services.suspension_reserva import upsert_suspension_reserva_dia


@frappe.whitelist()
def suspender_reserva_dia(
	fecha: str,
	reserva_espacio: str,
	motivo: str | None = None,
) -> dict[str, Any]:
	"""Suspende Reserva Espacio Confirmada solo ese día."""
	ensure_spaces_write_access()
	if not frappe.has_permission("Suspension Reserva Dia", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	name = upsert_suspension_reserva_dia(
		fecha=fecha,
		reserva_espacio=reserva_espacio,
		motivo=motivo,
	)
	return {"name": name}
