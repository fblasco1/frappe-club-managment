"""API autenticada de reservas de espacios para el portal del socio."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.services.portal_reservas import (
	get_espacios_disponibles as _get_espacios_disponibles,
	get_reserva_propia as _get_reserva_propia,
	list_reservas_propias as _list_reservas_propias,
	solicitar_reserva_espacio as _solicitar_reserva_espacio,
)
from club_management.spaces.services.confirmacion_reservas import (
	adjuntar_comprobante_reserva as _adjuntar_comprobante,
)


@frappe.whitelist()
def get_espacios_disponibles(
	fecha: str,
	tipo_espacio: str | None = None,
) -> dict[str, Any]:
	"""Grilla horaria de slots libres/ocupados para espacios alquilables."""
	return _get_espacios_disponibles(fecha=fecha, tipo_espacio=tipo_espacio or None)


@frappe.whitelist()
def solicitar_reserva_espacio(
	espacio: str,
	fecha: str,
	hora_inicio: str,
	hora_fin: str,
	espacios_extra: str | list | None = None,
) -> dict[str, Any]:
	"""Solicita reserva: bloquea slot, vincula Socio de sesión y genera cargo borrador.

	Identidad solo de `frappe.session.user` (sin parámetro `socio` del cliente).
	`espacios_extra`: JSON list / CSV de espacios adicionales (mismo horario).
	"""
	return _solicitar_reserva_espacio(
		espacio=espacio,
		fecha=fecha,
		hora_inicio=hora_inicio,
		hora_fin=hora_fin,
		espacios_extra=espacios_extra,
	)


@frappe.whitelist()
def list_reservas_propias() -> list[dict[str, Any]]:
	"""Lista reservas del socio autenticado."""
	return _list_reservas_propias()


@frappe.whitelist()
def get_reserva_propia(reserva: str) -> dict[str, Any]:
	"""Detalle de una reserva propia."""
	return _get_reserva_propia(reserva)


@frappe.whitelist()
def adjuntar_comprobante_reserva(reserva: str, file_url: str) -> dict[str, Any]:
	"""Adjunta PDF de transferencia a una reserva propia Pendiente."""
	return _adjuntar_comprobante(reserva=reserva, file_url=file_url)
