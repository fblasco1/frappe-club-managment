"""DocType Suspension Reserva Dia: omitir reserva Confirmada solo en una fecha."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class SuspensionReservaDia(Document):
	def validate(self) -> None:
		if not self.fecha:
			frappe.throw(_("La fecha es obligatoria"), frappe.ValidationError)
		if not self.reserva_espacio:
			frappe.throw(_("Indicá la reserva a suspender"), frappe.ValidationError)
		if not frappe.db.exists("Reserva Espacio", self.reserva_espacio):
			frappe.throw(_("Reserva Espacio inexistente"), frappe.ValidationError)
		if frappe.db.get_value("Reserva Espacio", self.reserva_espacio, "estado") != "Confirmada":
			frappe.throw(
				_("Solo se pueden suspender reservas Confirmada"),
				frappe.ValidationError,
			)
		self._assert_unique_activa()

	def _assert_unique_activa(self) -> None:
		if (self.estado or "").strip() != "Activa":
			return
		existing = frappe.db.get_value(
			"Suspension Reserva Dia",
			{
				"fecha": self.fecha,
				"reserva_espacio": self.reserva_espacio,
				"estado": "Activa",
			},
			"name",
		)
		if existing and existing != self.name:
			frappe.throw(
				_("Ya hay una suspensión activa para esa reserva el {0}: {1}").format(
					self.fecha, existing
				),
				frappe.ValidationError,
			)
