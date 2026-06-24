"""API Desk — conceptos sugeridos para cargo extra (Secretaría)."""

from __future__ import annotations

import frappe

from club_management.members.services.cargo_extra_conceptos import (
	conceptos_cargo_extra_socio,
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
