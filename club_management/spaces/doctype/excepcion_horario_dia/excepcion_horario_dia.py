"""DocType Excepcion Horario Dia: ajuste puntual sin tocar grilla semanal."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.spaces.availability import validate_time_range

ACCIONES = frozenset({"Reubicar", "Suspender"})


class ExcepcionHorarioDia(Document):
	def validate(self) -> None:
		if not self.fecha:
			frappe.throw(_("La fecha es obligatoria"), frappe.ValidationError)
		if not self.espacio_origen:
			frappe.throw(_("Espacio origen es obligatorio"), frappe.ValidationError)
		if not (self.horario_row or "").strip():
			frappe.throw(_("Indicá la fila de Horario Entrenamiento"), frappe.ValidationError)

		accion = (self.accion or "Reubicar").strip()
		if accion not in ACCIONES:
			frappe.throw(_("Acción no permitida: {0}").format(accion), frappe.ValidationError)
		self.accion = accion

		if accion == "Suspender":
			self.espacio_destino = None
			self.hora_desde = None
			self.hora_hasta = None
		else:
			if not self.espacio_destino:
				frappe.throw(_("Espacio destino es obligatorio"), frappe.ValidationError)
			validate_time_range(self.hora_desde, self.hora_hasta)

		self._fill_titulo_origen()
		self._assert_unique_activa()

	def _fill_titulo_origen(self) -> None:
		if self.titulo_origen:
			return
		titulo = frappe.db.get_value("Horario Entrenamiento", self.horario_row, "titulo")
		if titulo:
			self.titulo_origen = str(titulo)

	def _assert_unique_activa(self) -> None:
		if (self.estado or "").strip() != "Activa":
			return
		filters = {
			"fecha": self.fecha,
			"horario_row": self.horario_row,
			"estado": "Activa",
		}
		existing = frappe.db.get_value("Excepcion Horario Dia", filters, "name")
		if existing and existing != self.name:
			frappe.throw(
				_("Ya hay una excepción activa para ese horario el {0}: {1}").format(
					self.fecha, existing
				),
				frappe.ValidationError,
			)
