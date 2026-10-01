"""DocType Bonificacion Recurrente — descuento de arancel aplicado al generar la deuda mensual."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class BonificacionRecurrente(Document):
	def validate(self) -> None:
		self._validate_valor()
		self._validate_vigencia()
		self._validate_grupo()
		if not (self.motivo or "").strip():
			frappe.throw(_("El motivo es obligatorio."))
		self._validate_sin_solapamiento()

	def _validate_valor(self) -> None:
		valor = flt(self.valor)
		if valor <= 0:
			frappe.throw(_("El valor del descuento debe ser mayor a cero."))
		if self.tipo_descuento == "Porcentaje" and valor > 100:
			frappe.throw(_("El porcentaje no puede superar 100."))

	def _validate_vigencia(self) -> None:
		if self.fecha_hasta and getdate(self.fecha_hasta) < getdate(self.fecha_desde):
			frappe.throw(_("La fecha hasta debe ser posterior a la fecha desde."))

	def _validate_grupo(self) -> None:
		if not self.grupo_actividad:
			return
		if frappe.db.get_value("Grupo Actividad", self.grupo_actividad, "actividad") != self.actividad:
			frappe.throw(_("El grupo no pertenece a la actividad seleccionada."))

	def _validate_sin_solapamiento(self) -> None:
		if self.estado != "Activa":
			return
		desde = getdate(self.fecha_desde)
		hasta = getdate(self.fecha_hasta) if self.fecha_hasta else None
		filters: dict = {
			"socio": self.socio,
			"actividad": self.actividad,
			"estado": "Activa",
			"name": ["!=", self.name or ""],
		}
		for row in frappe.get_all(
			"Bonificacion Recurrente",
			filters=filters,
			fields=["name", "fecha_desde", "fecha_hasta"],
		):
			otro_desde = getdate(row.fecha_desde)
			otro_hasta = getdate(row.fecha_hasta) if row.fecha_hasta else None
			empieza_antes_de_que_termine = hasta is None or otro_desde <= hasta
			termina_despues_de_que_empiece = otro_hasta is None or otro_hasta >= desde
			if empieza_antes_de_que_termine and termina_despues_de_que_empiece:
				frappe.throw(
					_("Ya existe una bonificación recurrente activa que se superpone: {0}").format(row.name)
				)
