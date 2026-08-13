"""Cargo extra facturable al socio (único o recurrente)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class CargoSocio(Document):
	def validate(self) -> None:
		if self.is_new() and not self.estado:
			self.estado = "Pendiente"
		self._validate_monto()
		self._validate_item()
		self._validate_vigencia()

	def _validate_monto(self) -> None:
		if flt(self.monto) <= 0:
			frappe.throw(_("El monto debe ser mayor a cero."))

	def _validate_item(self) -> None:
		if not self.item or not frappe.db.exists("Item", self.item):
			frappe.throw(_("Indique un ítem ERPNext válido."))
		if frappe.db.get_value("Item", self.item, "is_stock_item"):
			frappe.throw(_("El ítem de cargo debe ser un servicio (no stock)."))

	def _validate_vigencia(self) -> None:
		if self.modo_cobro == "Recurrente" and not self.fecha_hasta:
			frappe.throw(_("Indique la fecha hasta para cargos recurrentes."))
		if self.fecha_desde and self.fecha_hasta:
			if getdate(self.fecha_hasta) < getdate(self.fecha_desde):
				frappe.throw(_("La fecha hasta debe ser posterior a la fecha desde."))

	def on_trash(self) -> None:
		if self.estado == "Facturado":
			frappe.throw(_("No se puede eliminar un cargo ya facturado. Cancele si aplica."))

	def after_insert(self) -> None:
		"""Cargo Único se factura automáticamente al crearse (spec
		cargo_extra_conceptos_y_facturacion.md). Los Recurrentes entran en la
		deuda mensual; el mes corriente se factura desde el diálogo Desk."""
		if self.modo_cobro != "Unico" or self.estado != "Pendiente":
			return
		if (
			frappe.flags.in_migrate
			or frappe.flags.in_install
			or frappe.flags.in_import
			or getattr(frappe.flags, "in_patch", False)
		):
			return
		from club_management.members.services.cobranza_manual import (
			erpnext_cobranza_disponible,
		)

		if not erpnext_cobranza_disponible():
			frappe.throw(_("ERPNext no está disponible para facturar el cargo extra."))
		from club_management.members.services.cargo_socio import facturar_cargo_socio

		result = facturar_cargo_socio(self.name)
		self.estado = "Facturado"
		self.sales_invoice = result["sales_invoice"]
