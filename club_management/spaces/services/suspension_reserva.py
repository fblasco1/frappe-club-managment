"""Servicio: suspensión puntual de Reserva Espacio."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate


def find_suspension_activa(fecha: str, reserva_espacio: str) -> str | None:
	return frappe.db.get_value(
		"Suspension Reserva Dia",
		{
			"fecha": getdate(fecha),
			"reserva_espacio": reserva_espacio,
			"estado": "Activa",
		},
		"name",
	)


def upsert_suspension_reserva_dia(
	*,
	fecha: str,
	reserva_espacio: str,
	motivo: str | None = None,
) -> str:
	"""Crea o actualiza suspensión Activa para fecha + reserva."""
	if not frappe.db.exists("Reserva Espacio", reserva_espacio):
		frappe.throw(_("Reserva Espacio inexistente"), frappe.ValidationError)
	if frappe.db.get_value("Reserva Espacio", reserva_espacio, "estado") != "Confirmada":
		frappe.throw(_("Solo se pueden suspender reservas Confirmada"), frappe.ValidationError)

	payload = {
		"fecha": getdate(fecha),
		"estado": "Activa",
		"reserva_espacio": reserva_espacio,
		"motivo": (motivo or "").strip() or None,
	}
	existing = find_suspension_activa(fecha, reserva_espacio)
	if existing:
		doc = frappe.get_doc("Suspension Reserva Dia", existing)
		for key, value in payload.items():
			setattr(doc, key, value)
		doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc({"doctype": "Suspension Reserva Dia", **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def get_suspended_reserva_names_for_date(fecha: str) -> set[str]:
	rows = frappe.get_all(
		"Suspension Reserva Dia",
		filters={"fecha": getdate(fecha), "estado": "Activa"},
		pluck="reserva_espacio",
	)
	return {str(name) for name in rows if name}
