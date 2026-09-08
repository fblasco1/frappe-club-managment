"""Registro inmutable de callbacks y cambios de estado del gateway."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.finance.services.payment_log import PROVIDERS

IMMUTABLE_FIELDS = (
	"event_key",
	"provider",
	"merchant_transaction_id",
	"gateway_transaction_id",
	"status_code",
	"status_description",
	"state_changed_at",
	"payment_log",
	"payment_entry",
	"processing_result",
	"event_payload_json",
)


class PaymentGatewayEvent(Document):
	def validate(self) -> None:
		if self.provider not in PROVIDERS:
			frappe.throw(_("Proveedor de pasarela no permitido"), frappe.ValidationError)
		if not self.is_new():
			for fieldname in IMMUTABLE_FIELDS:
				previous = frappe.db.get_value(self.doctype, self.name, fieldname)
				if (previous or "") != (self.get(fieldname) or ""):
					frappe.throw(
						_("Payment Gateway Event es inmutable"),
						frappe.ValidationError,
					)

	def on_trash(self) -> None:
		frappe.throw(
			_("Payment Gateway Event es inmutable y no se puede eliminar"),
			frappe.ValidationError,
		)
