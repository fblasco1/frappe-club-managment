"""Servicio idempotente de Payment Log (Cobrand / Banco Supervielle)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

PROVIDER_SUPERVIELLE = "Banco Supervielle"
PROVIDERS = frozenset({"Cobrand", PROVIDER_SUPERVIELLE})
STATUSES = frozenset({"Recibido", "Conciliado", "Rechazado"})


def record_gateway_transaction(
	*,
	gateway_transaction_id: str | None = None,
	merchant_transaction_id: str | None = None,
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
	merchant_id = (merchant_transaction_id or "").strip()
	if not tid and not merchant_id:
		frappe.throw(_("Se requiere ID SICLUB o del gateway"), frappe.ValidationError)
	if provider not in PROVIDERS:
		frappe.throw(_("Proveedor de pasarela no permitido"), frappe.ValidationError)
	if status not in STATUSES:
		frappe.throw(_("Estado de Payment Log no permitido"), frappe.ValidationError)

	existing = None
	if merchant_id:
		existing = frappe.db.get_value(
			"Payment Log",
			{"merchant_transaction_id": merchant_id},
			["name", "gateway_reference", "provider", "sales_invoice", "gateway_transaction_id"],
			as_dict=True,
		)
	if not existing and tid:
		existing = frappe.db.get_value(
			"Payment Log",
			{"gateway_transaction_id": tid},
			["name", "gateway_reference", "provider", "sales_invoice", "gateway_transaction_id"],
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
		if existing.provider != provider:
			frappe.throw(_("El ID ya pertenece a otro proveedor"), frappe.ValidationError)
		if existing.sales_invoice and sales_invoice and existing.sales_invoice != sales_invoice:
			frappe.throw(_("El ID ya pertenece a otra factura"), frappe.ValidationError)
		if tid and existing.gateway_transaction_id and existing.gateway_transaction_id != tid:
			frappe.throw(_("El ID SICLUB ya tiene otro ID bancario"), frappe.ValidationError)
		return frappe.get_doc("Payment Log", existing.name)

	doc = frappe.get_doc(
		{
			"doctype": "Payment Log",
			"gateway_transaction_id": tid or None,
			"merchant_transaction_id": merchant_id or None,
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
	try:
		doc.insert(ignore_permissions=ignore_permissions)
	except frappe.DuplicateEntryError:
		lookup = (
			{"merchant_transaction_id": merchant_id}
			if merchant_id
			else {"gateway_transaction_id": tid}
		)
		concurrent_name = frappe.db.get_value("Payment Log", lookup, "name")
		if not concurrent_name:
			raise
		return record_gateway_transaction(
			gateway_transaction_id=tid or None,
			merchant_transaction_id=merchant_id or None,
			provider=provider,
			gateway_reference=gateway_reference,
			sales_invoice=sales_invoice,
			payment_entry=payment_entry,
			socio=socio,
			amount=amount,
			currency=currency,
			payload=payload,
			status=status,
			ignore_permissions=ignore_permissions,
		)
	return doc


def reconcile_gateway_transaction(
	log: Document,
	*,
	gateway_transaction_id: str,
	status: str,
	payment_entry: str | None = None,
) -> Document:
	"""Completa el ID bancario una vez y avanza la conciliación."""
	tid = (gateway_transaction_id or "").strip()
	if not tid:
		frappe.throw(_("gateway_transaction_id es obligatorio"), frappe.ValidationError)
	other = frappe.db.get_value(
		"Payment Log",
		{"gateway_transaction_id": tid},
		"name",
	)
	if other and other != log.name:
		frappe.throw(_("El ID bancario ya pertenece a otro pago"), frappe.ValidationError)
	if log.gateway_transaction_id and log.gateway_transaction_id != tid:
		frappe.throw(_("El Payment Log ya tiene otro ID bancario"), frappe.ValidationError)
	log.gateway_transaction_id = tid
	log.status = status
	if payment_entry:
		if log.payment_entry and log.payment_entry != payment_entry:
			frappe.throw(_("El Payment Log ya tiene otro Payment Entry"), frappe.ValidationError)
		log.payment_entry = payment_entry
	log.save(ignore_permissions=True)
	return log
