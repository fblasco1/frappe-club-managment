"""API Desk — dashboard de Gestión de Espacios y Canchas."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.permissions import ensure_spaces_read_access
from club_management.spaces.services.espacios_desk_dashboard import (
	get_espacios_desk_dashboard_payload,
)


@frappe.whitelist()
def get_espacios_desk_dashboard(
	fecha: str | None = None,
	espacio: str | None = None,
) -> dict[str, Any]:
	"""Pendientes de reserva + agenda del día (filtro opcional por espacio)."""
	ensure_spaces_read_access()
	if not frappe.has_permission("Espacio", "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	if not frappe.has_permission("Reserva Espacio", "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return get_espacios_desk_dashboard_payload(fecha=fecha, espacio=espacio or None)
