"""API Desk — liquidación por equipo y rango de fechas."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.services.liquidacion_equipo import (
	get_facturas_pendientes_socio_en_rango,
	liquidar_deuda_socio_en_rango,
	registrar_cobro_liquidacion,
)
from club_management.members.services.socio_operaciones_secretaria import ensure_secretaria_operacion_access


@frappe.whitelist()
def get_facturas_pendientes_rango(
	socio: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> list[dict[str, Any]]:
	ensure_secretaria_operacion_access()
	return get_facturas_pendientes_socio_en_rango(socio, fecha_desde, fecha_hasta)


@frappe.whitelist()
def registrar_cobro_liquidacion_desk(
	socio: str,
	sales_invoice: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	ensure_secretaria_operacion_access()
	result = registrar_cobro_liquidacion(socio, sales_invoice, fecha_desde, fecha_hasta)
	return {"status": "ok", **result}


@frappe.whitelist()
def liquidar_deuda_socio_en_rango_desk(
	socio: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	ensure_secretaria_operacion_access()
	result = liquidar_deuda_socio_en_rango(socio, fecha_desde, fecha_hasta)
	return {"status": "ok", **result}
