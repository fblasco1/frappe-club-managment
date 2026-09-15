"""API Desk: cola y confirmación/rechazo de reservas (Coordinación)."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.services.confirmacion_reservas import (
	confirmar_reserva_espacio as _confirmar,
	list_reservas_pendientes_confirmacion as _list_pendientes,
	rechazar_reserva_espacio as _rechazar,
)


@frappe.whitelist()
def list_reservas_pendientes_confirmacion() -> list[dict[str, Any]]:
	"""Cola de reservas Pendiente para Coordinación."""
	return _list_pendientes()


@frappe.whitelist()
def confirmar_reserva_espacio(reserva: str) -> dict[str, Any]:
	"""Confirma una reserva Pendiente (ocupación firme)."""
	return _confirmar(reserva)


@frappe.whitelist()
def rechazar_reserva_espacio(reserva: str, motivo: str) -> dict[str, Any]:
	"""Rechaza una reserva Pendiente y libera el slot."""
	return _rechazar(reserva=reserva, motivo=motivo)
