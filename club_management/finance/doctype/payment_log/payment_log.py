"""Payment Log: registro inmutable de IDs de transacción del gateway."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.finance.services.payment_log import PROVIDERS

IMMUTABLE_FIELDS = ("gateway_transaction_id", "provider", "gateway_reference")


class PaymentLog(Document):
	def validate(self) -> None:
		provider = (self.provider or "").strip()
		if provider not in PROVIDERS:
			frappe.throw(_("Proveedor de pasarela no permitido"), frappe.ValidationError)
		if not (self.gateway_transaction_id or "").strip():
			frappe.throw(_("gateway_transaction_id es obligatorio"), frappe.ValidationError)
		if not self.is_new():
			self._assert_immutable_fields()

	def on_trash(self) -> None:
		frappe.throw(_("Payment Log es inmutable y no se puede eliminar"), frappe.ValidationError)

	def _assert_immutable_fields(self) -> None:
		if not self.name:
			return
		for fieldname in IMMUTABLE_FIELDS:
			previous = frappe.db.get_value("Payment Log", self.name, fieldname)
			current = self.get(fieldname)
			if (previous or "") != (current or ""):
				frappe.throw(
					_("El campo {0} de Payment Log es inmutable").format(fieldname),
					frappe.ValidationError,
				)
