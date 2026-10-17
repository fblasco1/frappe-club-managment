"""Alias inglés del canal guest de alquiler externo.

Spec: `club_management/specs/reservas_espacio_externo.md`

La implementación canónica vive en `externo_reservas`; este módulo reexporta
los whitelist methods para el contrato documentado como `external_booking`.
"""

from __future__ import annotations

from club_management.spaces.api.externo_reservas import (  # noqa: F401
	abrir_sesion_reserva_externa,
	adjuntar_comprobante_externo,
	get_espacios_disponibles_externo,
	get_reserva_externa,
	solicitar_reserva_externa,
	upload_y_adjuntar_comprobante_externo,
)
