"""Reasignación controlada de `numero_socio` (PK del Socio).

Spec: `club_management/specs/corregir_numero_socio.md`
"""

from __future__ import annotations

import frappe
from frappe import _

from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


def corregir_numero_socio(socio: str, nuevo_numero: int | str) -> str:
	"""Renombra un Socio al nuevo número y sincroniza el campo `numero_socio`.

	Returns:
		El nuevo `name` del documento.
	"""
	ensure_secretaria_operacion_access()

	socio_name = str(socio or "").strip()
	if not socio_name:
		frappe.throw(_("Indique el socio a corregir."), frappe.ValidationError)
	if not frappe.db.exists("Socio", socio_name):
		frappe.throw(_("Socio {0} no existe.").format(socio_name), frappe.DoesNotExistError)

	try:
		destino = int(nuevo_numero)
	except (TypeError, ValueError):
		frappe.throw(_("Número de socio inválido."), frappe.ValidationError)
	if destino <= 0:
		frappe.throw(_("El número de socio debe ser un entero positivo."), frappe.ValidationError)

	nuevo_name = str(destino)
	if socio_name == nuevo_name:
		# Idempotente: ya está en el número pedido.
		frappe.db.set_value("Socio", socio_name, "numero_socio", destino, update_modified=False)
		return socio_name

	if frappe.db.exists("Socio", nuevo_name):
		frappe.throw(
			_("El número de socio {0} ya está asignado a otro socio.").format(destino),
			frappe.ValidationError,
		)

	frappe.rename_doc(
		"Socio",
		socio_name,
		nuevo_name,
		force=True,
		merge=False,
	)
	frappe.db.set_value("Socio", nuevo_name, "numero_socio", destino, update_modified=False)
	return nuevo_name
