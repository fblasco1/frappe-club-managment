"""Servicio idempotente de Payment Log (Cobrand / Banco Supervielle)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

PROVIDERS = frozenset({"Cobrand", "Banco Supervielle"})
STATUSES = frozenset({"Recibido", "Conciliado", "Rechazado"})


def record_gateway_transaction(
	*,
	gateway_transaction_id: str,
	provider: str,
	gateway_reference: str | None = None,
	sales_invoice: str | None = None,
	payment_entry: str | None = None,
	socio: str | None = None,
	amount: float | None = None,
	currency: str = "ARS",
	payload: dict[str, Any] | None = None,
	status: str = "Recibido",
	ignore_permissions: bool = False,
) -> Document:
	"""Inserta o reutiliza un Payment Log. Nunca reasigna el ID a otro pago."""
	tid = (gateway_transaction_id or "").strip()
	if not tid:
		frappe.throw(_("gateway_transaction_id es obligatorio"), frappe.ValidationError)
	if provider not in PROVIDERS:
		frappe.throw(_("Proveedor de pasarela no permitido"), frappe.ValidationError)
	if status not in STATUSES:
		frappe.throw(_("Estado de Payment Log no permitido"), frappe.ValidationError)

	existing = frappe.db.get_value(
		"Payment Log",
		{"gateway_transaction_id": tid},
		["name", "gateway_reference"],
		as_dict=True,
	)
	if existing:
		prev_ref = (existing.gateway_reference or "").strip()
		new_ref = (gateway_reference or "").strip()
		if prev_ref and new_ref and prev_ref != new_ref:
			frappe.throw(
				_("El ID de transacción ya está asociado a otro pago"),
				frappe.ValidationError,
			)
		return frappe.get_doc("Payment Log", existing.name)

	doc = frappe.get_doc(
		{
			"doctype": "Payment Log",
			"gateway_transaction_id": tid,
			"provider": provider,
			"status": status,
			"gateway_reference": (gateway_reference or "").strip() or None,
			"sales_invoice": sales_invoice or None,
			"payment_entry": payment_entry or None,
			"socio": socio or None,
			"amount": amount,
			"currency": currency or "ARS",
			"payload_json": payload,
			"received_at": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=ignore_permissions)
	return doc
