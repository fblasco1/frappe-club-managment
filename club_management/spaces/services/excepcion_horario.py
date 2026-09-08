"""Servicio: reubicación o suspensión puntual de entrenamiento (sin tocar grilla)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate

from club_management.spaces.availability import validate_time_range


def find_excepcion_activa(fecha: str, horario_row: str) -> str | None:
	return frappe.db.get_value(
		"Excepcion Horario Dia",
		{
			"fecha": getdate(fecha),
			"horario_row": horario_row,
			"estado": "Activa",
		},
		"name",
	)


def _assert_horario_row(espacio_origen: str, horario_row: str) -> str:
	if not frappe.db.exists("Horario Entrenamiento", horario_row):
		frappe.throw(_("Horario de entrenamiento inexistente"), frappe.ValidationError)
	parent = frappe.db.get_value(
		"Horario Entrenamiento", horario_row, ["parent", "titulo"], as_dict=True
	)
	if not parent or parent.parent != espacio_origen:
		frappe.throw(
			_("La fila de horario no pertenece al espacio origen"),
			frappe.ValidationError,
		)
	return str(parent.titulo or "")


def upsert_excepcion_horario_dia(
	*,
	fecha: str,
	espacio_origen: str,
	horario_row: str,
	accion: str = "Reubicar",
	espacio_destino: str | None = None,
	hora_desde: str | None = None,
	hora_hasta: str | None = None,
	motivo: str | None = None,
) -> str:
	"""Crea o actualiza excepción Activa para fecha + fila de horario."""
	accion = (accion or "Reubicar").strip()
	if accion not in {"Reubicar", "Suspender"}:
		frappe.throw(_("Acción no permitida"), frappe.ValidationError)
	if not frappe.db.exists("Espacio", espacio_origen):
		frappe.throw(_("Espacio origen inexistente"), frappe.ValidationError)
	if accion == "Reubicar":
		if not espacio_destino or not frappe.db.exists("Espacio", espacio_destino):
			frappe.throw(_("Espacio destino inexistente"), frappe.ValidationError)
		validate_time_range(hora_desde, hora_hasta)

	titulo_origen = _assert_horario_row(espacio_origen, horario_row)

	payload: dict[str, Any] = {
		"fecha": getdate(fecha),
		"estado": "Activa",
		"accion": accion,
		"espacio_origen": espacio_origen,
		"horario_row": horario_row,
		"titulo_origen": titulo_origen,
		"motivo": (motivo or "").strip() or None,
	}
	if accion == "Reubicar":
		payload.update(
			{
				"espacio_destino": espacio_destino,
				"hora_desde": hora_desde,
				"hora_hasta": hora_hasta,
			}
		)
	else:
		payload.update(
			{
				"espacio_destino": None,
				"hora_desde": None,
				"hora_hasta": None,
			}
		)

	existing = find_excepcion_activa(fecha, horario_row)
	if existing:
		doc = frappe.get_doc("Excepcion Horario Dia", existing)
		for key, value in payload.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc({"doctype": "Excepcion Horario Dia", **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def suspender_horario_dia(
	*,
	fecha: str,
	espacio_origen: str,
	horario_row: str,
	motivo: str | None = None,
) -> str:
	"""Omite el entrenamiento de grilla solo ese día (sin bloque destino)."""
	return upsert_excepcion_horario_dia(
		fecha=fecha,
		espacio_origen=espacio_origen,
		horario_row=horario_row,
		accion="Suspender",
		motivo=motivo,
	)
