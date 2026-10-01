"""API Desk — gimnasio: practicantes No Socio, Quincena y Entrenamiento por hora (Secretaría)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from club_management.members.services.gimnasio_pases import (
	generar_cargo_gimnasio,
	precios_gimnasio,
)
from club_management.members.services.practicante_no_socio import (
	convertir_no_socio_a_socio,
	crear_practicante_no_socio,
)
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


@frappe.whitelist()
def precios_pases_gimnasio() -> dict[str, float]:
	ensure_secretaria_operacion_access()
	return precios_gimnasio()


@frappe.whitelist()
def generar_cargo_gimnasio_desk(
	socio: str,
	tipo: str,
	registrar_pago: int | str = 0,
	mode_of_payment: str | None = None,
	monto: float | str | None = None,
) -> dict[str, Any]:
	"""Genera Quincena / Entrenamiento por hora y opcionalmente registra el pago en el mismo paso."""
	ensure_secretaria_operacion_access()
	if not frappe.has_permission("Cargo Socio", "create"):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if not socio or not frappe.db.exists("Socio", socio):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	frappe.has_permission("Socio", "read", doc=socio, throw=True)
	return generar_cargo_gimnasio(
		socio,
		tipo,
		registrar_pago=bool(cint(registrar_pago)),
		mode_of_payment=mode_of_payment or None,
		monto=flt(monto) if monto else None,
	)


@frappe.whitelist()
def crear_practicante_no_socio_desk(datos: str | dict) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	if not frappe.has_permission("Socio", "create"):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	payload = frappe.parse_json(datos) if isinstance(datos, str) else datos
	return {"socio": crear_practicante_no_socio(payload or {})}


@frappe.whitelist()
def convertir_no_socio_a_socio_desk(socio: str, categoria: str) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	if not socio or not frappe.db.exists("Socio", socio):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	frappe.has_permission("Socio", "write", doc=socio, throw=True)
	return {"socio": convertir_no_socio_a_socio(socio, categoria=categoria)}
