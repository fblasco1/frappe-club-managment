"""API guest de reservas externas (allow_guest + gate token/canal).

Spec: `club_management/specs/reservas_espacio_externo.md`
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.services.externo_reservas import (
	adjuntar_comprobante_externo as _adjuntar,
	abrir_sesion_reserva_externa as _abrir_sesion,
	get_espacios_disponibles_externo as _get_disponibles,
	get_reserva_externa as _get_reserva,
	solicitar_reserva_externa as _solicitar,
	upload_y_adjuntar_comprobante_externo as _upload_adjuntar,
)


@frappe.whitelist(allow_guest=True)
def abrir_sesion_reserva_externa() -> dict[str, Any]:
	"""Abre sesión firmada si el canal externo está habilitado."""
	return _abrir_sesion()


@frappe.whitelist(allow_guest=True)
def get_espacios_disponibles_externo(
	sesion_token: str,
	fecha: str,
	tipo_espacio: str | None = None,
) -> dict[str, Any]:
	"""Grilla de disponibilidad con tarifa externa."""
	return _get_disponibles(
		sesion_token=sesion_token,
		fecha=fecha,
		tipo_espacio=tipo_espacio or None,
	)


@frappe.whitelist(allow_guest=True)
def solicitar_reserva_externa(
	sesion_token: str,
	espacio: str,
	fecha: str,
	hora_inicio: str,
	hora_fin: str,
	arrendatario_nombre: str,
	arrendatario_contacto: str,
) -> dict[str, Any]:
	"""Solicita Alquiler externo Temporal Pendiente y devuelve token_acceso."""
	return _solicitar(
		sesion_token=sesion_token,
		espacio=espacio,
		fecha=fecha,
		hora_inicio=hora_inicio,
		hora_fin=hora_fin,
		arrendatario_nombre=arrendatario_nombre,
		arrendatario_contacto=arrendatario_contacto,
	)


@frappe.whitelist(allow_guest=True)
def get_reserva_externa(token_acceso: str) -> dict[str, Any]:
	"""Detalle acotado por token_acceso."""
	return _get_reserva(token_acceso)


@frappe.whitelist(allow_guest=True)
def adjuntar_comprobante_externo(token_acceso: str, file_url: str) -> dict[str, Any]:
	"""Adjunta PDF de transferencia a la reserva del token."""
	return _adjuntar(token_acceso=token_acceso, file_url=file_url)


@frappe.whitelist(allow_guest=True)
def upload_y_adjuntar_comprobante_externo(
	token_acceso: str,
	filename: str,
	content_b64: str,
) -> dict[str, Any]:
	"""Sube PDF (base64) y lo adjunta a la reserva externa (gate: token_acceso)."""
	return _upload_adjuntar(
		token_acceso=token_acceso,
		filename=filename,
		content_b64=content_b64,
	)
