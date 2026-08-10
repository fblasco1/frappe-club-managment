"""Configuración operativa del club (cuotas, empresa ERPNext, cobranza)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

_MIN_DIA_MES = 1
_MAX_DIA_MES = 28
_SEGUNDO_VENCIMIENTO_OPCIONES = frozenset(
	{"Ultimo dia del mes", *(str(d) for d in range(15, 29))}
)


class ClubSettings(Document):
	def validate(self) -> None:
		self._aplicar_defaults_cobranza()
		self._validate_calendario_cobranza()

	def _aplicar_defaults_cobranza(self) -> None:
		if self.dia_generacion_deuda is None:
			self.dia_generacion_deuda = 1
		if self.dia_primer_vencimiento is None:
			self.dia_primer_vencimiento = 10
		if not self.dia_segundo_vencimiento:
			self.dia_segundo_vencimiento = "20"
		if self.recargo_segundo_vencimiento_pct is None:
			self.recargo_segundo_vencimiento_pct = 10
		if self.recargo_mes_vencido_pct is None:
			self.recargo_mes_vencido_pct = 5
		if self.recargo_post_vencimiento_pct is None:
			self.recargo_post_vencimiento_pct = 10
		if self.incluir_aranceles_en_deuda_mensual is None:
			self.incluir_aranceles_en_deuda_mensual = 1
		if self.incluir_cargos_extra_en_deuda_mensual is None:
			self.incluir_cargos_extra_en_deuda_mensual = 1

	def _validate_calendario_cobranza(self) -> None:
		gen = int(self.dia_generacion_deuda or 1)
		v1 = int(self.dia_primer_vencimiento or 10)

		for label, value in (
			(_("Día generación de deuda"), gen),
			(_("Día primer vencimiento"), v1),
		):
			if not _MIN_DIA_MES <= value <= _MAX_DIA_MES:
				frappe.throw(
					_("{0} debe estar entre {1} y {2}.").format(
						label, _MIN_DIA_MES, _MAX_DIA_MES
					)
				)

		if v1 <= gen:
			frappe.throw(
				_(
					"El primer vencimiento debe ser posterior al día de generación de deuda."
				)
			)

		segundo = (self.dia_segundo_vencimiento or "20").strip()
		if segundo not in _SEGUNDO_VENCIMIENTO_OPCIONES:
			frappe.throw(_("Segundo vencimiento inválido."))

		for label, value in (
			(_("Recargo 2.º vencimiento (%) — legado"), float(self.recargo_segundo_vencimiento_pct or 0)),
			(_("Recargo extra post 2.º vencimiento (%)"), float(self.recargo_mes_vencido_pct or 0)),
			(_("Recargo post 1.er vencimiento (%)"), float(self.recargo_post_vencimiento_pct or 0)),
		):
			if value < 0 or value > 100:
				frappe.throw(_("{0} debe estar entre 0% y 100%.").format(label))
