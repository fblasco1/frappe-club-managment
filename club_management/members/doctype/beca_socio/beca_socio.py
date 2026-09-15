"""DocType Beca Socio — descuentos/exenciones en cobranza mensual."""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, getdate


class BecaSocio(Document):
	def validate(self) -> None:
		self._validate_vigencia()
		self._validate_porcentajes()
		self._aplicar_defaults_tipo()

	def _validate_vigencia(self) -> None:
		if self.fecha_desde and self.fecha_hasta:
			if getdate(self.fecha_hasta) < getdate(self.fecha_desde):
				frappe.throw(_("La fecha hasta debe ser posterior a la fecha desde."))

	def _validate_porcentajes(self) -> None:
		for field in ("pct_cuota_social", "pct_arancel"):
			value = float(self.get(field) or 0)
			if value < 0 or value > 100:
				frappe.throw(_("{0} debe estar entre 0 y 100.").format(self.meta.get_label(field)))

	def _aplicar_defaults_tipo(self) -> None:
		if self.tipo_beca == "Total":
			self.pct_cuota_social = 100
			self.pct_arancel = 100
		elif self.tipo_beca == "Parcial Exime Cuota":
			self.pct_cuota_social = 100
			self.pct_arancel = 0
		elif self.tipo_beca == "Parcial Exime Arancel":
			self.pct_cuota_social = 0
			self.pct_arancel = 100

	def before_save(self) -> None:
		if not self.fecha_hasta and self.fecha_desde:
			self.fecha_hasta = add_months(self.fecha_desde, 6)
