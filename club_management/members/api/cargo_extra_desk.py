"""API Desk — conceptos sugeridos y prepago de cargo extra (Secretaría)."""

from __future__ import annotations

import frappe

from club_management.members.services.cargo_extra_conceptos import (
	conceptos_cargo_extra_socio,
)
from club_management.members.services.cargo_extra_prepago import (
	list_meses_prepago_cargo,
	prepagar_cargo_socio,
)
from club_management.members.services.cargo_socio import (
	crear_cargo_extra_socio,
	facturar_mes_corriente_cargo,
)
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


@frappe.whitelist()
def list_conceptos_cargo_extra(socio: str) -> list[dict[str, str]]:
	"""Lista de conceptos (ítems) ofrecibles como cargo extra para el socio."""
	ensure_secretaria_operacion_access()
	if not socio or not frappe.db.exists("Socio", socio):
		frappe.throw(frappe._("Socio no encontrado"), frappe.DoesNotExistError)
	return conceptos_cargo_extra_socio(socio)


@frappe.whitelist()
def list_meses_prepago(cargo: str, reference_date: str | None = None) -> list[dict]:
	ensure_secretaria_operacion_access()
	return list_meses_prepago_cargo(cargo, reference_date=reference_date)


@frappe.whitelist()
def prepagar_cargo(
	cargo: str,
	periodos: str | list | None = None,
	reference_date: str | None = None,
) -> dict:
	ensure_secretaria_operacion_access()
	parsed: list[str] | None
	if periodos is None or periodos == "" or periodos == "__all__":
		parsed = None
	elif isinstance(periodos, str):
		parsed = [str(x) for x in (frappe.parse_json(periodos) or [])]
	else:
		parsed = [str(x) for x in periodos]
	return prepagar_cargo_socio(cargo, periodos=parsed, reference_date=reference_date)


@frappe.whitelist()
def facturar_mes_corriente(cargo: str, reference_date: str | None = None) -> dict:
	"""Factura el mes corriente de un cargo recurrente para poder cobrarlo."""
	ensure_secretaria_operacion_access()
	return facturar_mes_corriente_cargo(cargo, reference_date=reference_date)


@frappe.whitelist()
def crear_cargo_extra(
	socio: str,
	titulo: str,
	tipo_cargo: str,
	modo_cobro: str,
	item: str,
	monto: float,
	fecha_desde: str | None = None,
	fecha_hasta: str | None = None,
	observaciones: str | None = None,
	facturar_mes_corriente: int = 1,
) -> dict:
	"""Crea el cargo extra desde Desk y lo deja cobrable."""
	ensure_secretaria_operacion_access()
	return crear_cargo_extra_socio(
		socio=socio,
		titulo=titulo,
		tipo_cargo=tipo_cargo,
		modo_cobro=modo_cobro,
		item=item,
		monto=float(monto or 0),
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		observaciones=observaciones,
		facturar_mes_corriente=bool(int(facturar_mes_corriente or 0)),
	)
