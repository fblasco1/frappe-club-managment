"""Servicio de conciliación para callbacks Botón de Pago Supervielle v2.6."""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal, InvalidOperation
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, get_datetime

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	reconcile_gateway_transaction,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError

CALLBACK_FIELDS = (
	"IdPago",
	"IdPagoPortal",
	"FechaHoraPago",
	"CodMedioPago",
	"MedioPago",
	"Importe",
	"CodigoEstado",
	"Estado",
	"FechaHoraCambioEstado",
	"CodigoRechazo",
	"Rechazo",
	"Cuotas",
	"CodigoAutorizacion",
	"Ticket",
	"Mail",
	"Observaciones",
)
_MAX_CALLBACK_BYTES = 64 * 1024
_AUDIT_ONLY_STATES = {"0", "1", "2", "3", "4"}
_CONCILE_STATE = "5"
_MANUAL_REVIEW_STATES = {"6", "7", "8", "9"}


def build_callback_hash(payload: dict[str, Any], secret_key: str) -> str:
	raw = "".join(str(payload.get(field) or "") for field in CALLBACK_FIELDS) + secret_key
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_callback_payload(payload: dict[str, Any], secret_key: str) -> dict[str, Any]:
	if not isinstance(payload, dict):
		raise SupervielleIntegrationError("Callback Supervielle debe ser un objeto JSON.")
	if len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) > _MAX_CALLBACK_BYTES:
		raise SupervielleIntegrationError("Callback Supervielle excede el tamaño permitido.")
	allowed = set(CALLBACK_FIELDS) | {"Hash"}
	if set(payload) != allowed:
		raise SupervielleIntegrationError("Callback Supervielle tiene campos faltantes o excedentes.")
	for field in ("IdPago", "IdPagoPortal", "Importe", "CodigoEstado", "FechaHoraCambioEstado"):
		if not str(payload.get(field) or "").strip():
			raise SupervielleIntegrationError(f"Callback Supervielle sin {field}.")
	expected = build_callback_hash(payload, secret_key)
	received = str(payload.get("Hash") or "").strip().lower()
	if not hmac.compare_digest(expected, received):
		raise SupervielleIntegrationError("Hash de callback Supervielle inválido.")
	try:
		get_datetime(payload["FechaHoraCambioEstado"])
		Decimal(str(payload["Importe"]).replace(",", "."))
	except (InvalidOperation, TypeError, ValueError) as exc:
		raise SupervielleIntegrationError("Fecha o importe inválido en callback Supervielle.") from exc
	return dict(payload)


def _event_key(payload: dict[str, Any]) -> str:
	identity = "|".join(
		[
			PROVIDER_SUPERVIELLE,
			str(payload["IdPagoPortal"]),
			str(payload["CodigoEstado"]),
			str(payload["FechaHoraCambioEstado"]),
		]
	)
	return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _load_payment_log(payload: dict[str, Any]) -> Any:
	name = frappe.db.get_value(
		"Payment Log",
		{"merchant_transaction_id": str(payload["IdPago"]).strip()},
		"name",
	)
	if not name:
		frappe.throw(_("No existe Payment Log para IdPago"), frappe.ValidationError)
	log = frappe.get_doc("Payment Log", name)
	if log.provider != PROVIDER_SUPERVIELLE:
		frappe.throw(_("IdPago pertenece a otro proveedor"), frappe.ValidationError)
	amount = flt(str(payload["Importe"]).replace(",", "."))
	if abs(flt(log.amount) - amount) > 0.005 or (log.currency or "ARS") != "ARS":
		frappe.throw(_("Importe o moneda no coincide con la publicación"), frappe.ValidationError)
	return log


def _lock_payment_log(name: str) -> Any:
	if frappe.db.db_type == "postgres":
		frappe.db.sql(
			'SELECT name FROM "tabPayment Log" WHERE name = %s FOR UPDATE',
			(name,),
		)
	return frappe.get_doc("Payment Log", name)


def _validate_transition(log: Any, payload: dict[str, Any]) -> None:
	status = str(payload["CodigoEstado"])
	if log.status == "Conciliado" and status != _CONCILE_STATE:
		frappe.throw(_("Transición inválida para un pago conciliado"), frappe.ValidationError)


def _create_payment_entry(log: Any, payload: dict[str, Any], settings: Any) -> str:
	if not log.sales_invoice:
		frappe.throw(_("Payment Log sin Sales Invoice"), frappe.ValidationError)
	invoice = frappe.get_doc("Sales Invoice", log.sales_invoice)
	amount = flt(str(payload["Importe"]).replace(",", "."))
	if invoice.docstatus != 1:
		frappe.throw(_("Sales Invoice no está presentada"), frappe.ValidationError)
	if abs(flt(invoice.outstanding_amount) - amount) > 0.005:
		frappe.throw(_("El pago debe coincidir con el saldo total de la factura"), frappe.ValidationError)
	try:
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
	except ImportError as exc:
		raise frappe.ValidationError(_("ERPNext no está disponible")) from exc
	pe = get_payment_entry("Sales Invoice", invoice.name, party_amount=amount)
	pe.mode_of_payment = settings.mode_of_payment
	pe.paid_to = settings.clearing_account
	pe.reference_no = str(payload["IdPagoPortal"])[:140]
	pe.reference_date = get_datetime(payload["FechaHoraPago"]).date()
	pe.remarks = _("Conciliación automática Supervielle {0}").format(payload["IdPagoPortal"])
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


def _insert_event(
	payload: dict[str, Any],
	log: Any,
	*,
	result: str,
	payment_entry: str | None = None,
) -> Any:
	snapshot = {key: value for key, value in payload.items() if key != "Hash"}
	doc = frappe.get_doc(
		{
			"doctype": "Payment Gateway Event",
			"event_key": _event_key(payload),
			"provider": PROVIDER_SUPERVIELLE,
			"merchant_transaction_id": payload["IdPago"],
			"gateway_transaction_id": payload["IdPagoPortal"],
			"status_code": payload["CodigoEstado"],
			"status_description": payload["Estado"],
			"state_changed_at": payload["FechaHoraCambioEstado"],
			"payment_log": log.name,
			"payment_entry": payment_entry,
			"processing_result": result,
			"event_payload_json": frappe.as_json(snapshot),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def process_callback(
	payload: dict[str, Any],
	*,
	secret_key: str | None = None,
	settings: Any | None = None,
) -> dict[str, Any]:
	if settings is None:
		from club_management.integrations.supervielle.client import get_runtime_settings

		settings = get_runtime_settings()
	secret = secret_key or settings.secret_key
	validated = validate_callback_payload(payload, secret)
	key = _event_key(validated)
	log = _load_payment_log(validated)
	log = _lock_payment_log(log.name)
	existing = frappe.db.get_value(
		"Payment Gateway Event",
		{"event_key": key},
		["name", "processing_result", "payment_entry", "merchant_transaction_id"],
		as_dict=True,
	)
	if existing:
		if existing.merchant_transaction_id != validated["IdPago"]:
			frappe.throw(_("El evento bancario pertenece a otro pago"), frappe.ValidationError)
		return {
			"status": "ok",
			"event": existing.name,
			"result": existing.processing_result,
			"payment_entry": existing.payment_entry,
			"replayed": True,
		}
	_validate_transition(log, validated)
	status_code = str(validated["CodigoEstado"])
	payment_entry = None
	if status_code == _CONCILE_STATE:
		if log.payment_entry:
			payment_entry = log.payment_entry
		else:
			payment_entry = _create_payment_entry(log, validated, settings)
		reconcile_gateway_transaction(
			log,
			gateway_transaction_id=validated["IdPagoPortal"],
			status="Conciliado",
			payment_entry=payment_entry,
		)
		result = "conciled"
	else:
		reconcile_gateway_transaction(
			log,
			gateway_transaction_id=validated["IdPagoPortal"],
			status="Recibido",
		)
		result = "manual_review" if status_code in _MANUAL_REVIEW_STATES else "audited"
	event = _insert_event(validated, log, result=result, payment_entry=payment_entry)
	return {
		"status": "ok",
		"event": event.name,
		"result": result,
		"payment_entry": payment_entry,
		"replayed": False,
	}
