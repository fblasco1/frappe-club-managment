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
