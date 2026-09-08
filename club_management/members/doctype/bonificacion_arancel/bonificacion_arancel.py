"""DocType Bonificacion Arancel — descuento puntual de arancel al cobro."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

_PERIODO_RE = re.compile(r"^(\d{2})/(\d{4})$")


class BonificacionArancel(Document):
	def validate(self) -> None:
		self._validate_periodo()
		self._validate_alcance()
		self._validate_valor()
		if not (self.motivo or "").strip():
			frappe.throw(_("El motivo es obligatorio."))

	def _validate_periodo(self) -> None:
		raw = (self.periodo_cobro or "").strip()
		if not _PERIODO_RE.match(raw):
			frappe.throw(_("Período inválido. Usá MM/YYYY (ej. 08/2026)."))
		self.periodo_cobro = raw

	def _validate_alcance(self) -> None:
		if self.socio:
			return
		if not (self.actividad or self.grupo_actividad or self.equipo_actividad):
			frappe.throw(
				_("Bonificación masiva: indicá Actividad, Grupo o Equipo (o un Socio para individual).")
			)

	def _validate_valor(self) -> None:
		valor = flt(self.valor)
		if valor <= 0:
			frappe.throw(_("El valor del descuento debe ser mayor a cero."))
		if self.tipo_descuento == "Porcentaje" and valor > 100:
			frappe.throw(_("El porcentaje no puede superar 100."))
