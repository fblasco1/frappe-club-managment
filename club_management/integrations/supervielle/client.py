"""Cliente Botón de Pago Supervielle v2.6 con auditoría idempotente."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

import frappe
import requests
from frappe import _
from frappe.utils import flt

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	record_gateway_transaction,
)
from club_management.integrations.supervielle.payload import (
	CheckoutSource,
	SupervielleRuntimeSettings,
	assert_sandbox_url_matches_mode,
	build_checkout_payload,
	extract_boton_pago_result,
	sign_payload,
	validate_response_hash,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.members.services.cobranza_manual import _campo_socio_en

_TIMEOUT_SECONDS = 30
_ALLOWED_ROLES = {"System Manager", "Tesoreria", "Secretaria"}


@dataclass(frozen=True)
class BotonPagoResult:
	url: str
	transaction_id: str
	response: dict[str, Any]


def _get_secret(settings_doc: Any) -> str:
	try:
		secret = settings_doc.get_password("secret_key", raise_exception=False)
	except TypeError:
		secret = settings_doc.get_password("secret_key")
	if not secret:
		frappe.throw(_("Falta Secret Key de Supervielle"), frappe.ValidationError)
	return str(secret)


def get_runtime_settings() -> SupervielleRuntimeSettings:
	settings = frappe.get_single("Supervielle Settings")
	runtime = SupervielleRuntimeSettings(
		sandbox_mode=bool(settings.sandbox_mode),
		secret_key=_get_secret(settings),
		cuit_emisor=str(settings.cuit_emisor or "").strip(),
		api_url=str(settings.api_url or "").strip(),
		concepto_default=str(settings.concepto_default or "").strip(),
		url_ok=str(settings.url_ok or "").strip(),
		url_error=str(settings.url_error or "").strip(),
		rendicion_api_url=str(settings.rendicion_api_url or "").strip(),
		convenio=str(settings.convenio or "").strip(),
		mode_of_payment=str(settings.mode_of_payment or "").strip(),
		clearing_account=str(settings.clearing_account or "").strip(),
	)
	for fieldname in (
		"cuit_emisor",
		"api_url",
		"concepto_default",
		"url_ok",
		"url_error",
		"rendicion_api_url",
		"convenio",
		"mode_of_payment",
		"clearing_account",
	):
		if not getattr(runtime, fieldname):
			frappe.throw(
				_("Falta configurar {0} en Supervielle Settings").format(fieldname),
				frappe.ValidationError,
			)
	assert_sandbox_url_matches_mode(sandbox_mode=runtime.sandbox_mode, api_url=runtime.api_url)
	assert_sandbox_url_matches_mode(
		sandbox_mode=runtime.sandbox_mode,
		api_url=runtime.rendicion_api_url,
	)
	return runtime


def _load_checkout_source(sales_invoice_name: str) -> CheckoutSource:
	if not frappe.db.exists("Sales Invoice", sales_invoice_name):
		frappe.throw(_("Factura no encontrada"), frappe.DoesNotExistError)
	invoice = frappe.get_doc("Sales Invoice", sales_invoice_name)
	if invoice.docstatus != 1:
		frappe.throw(_("La factura debe estar presentada"), frappe.ValidationError)
	amount = flt(invoice.outstanding_amount)
	if amount <= 0:
		frappe.throw(_("La factura no tiene saldo pendiente"), frappe.ValidationError)
	campo_socio = _campo_socio_en("Sales Invoice")
	socio_name = invoice.get(campo_socio) if campo_socio else None
	if not socio_name:
		frappe.throw(_("La factura no está vinculada a un Socio"), frappe.ValidationError)
	socio = frappe.get_doc("Socio", socio_name)
	numero = str(socio.get("numero_socio") or socio.name).strip()
	dni = str(socio.get("dni") or socio.get("numero_documento") or "").strip()
	nombre = str(socio.get("nombre_completo") or socio.get("nombre") or socio.name).strip()
	email = str(socio.get("email") or socio.get("email_id") or "").strip()
	return CheckoutSource(
		invoice_name=invoice.name,
		amount=amount,
		due_date=str(invoice.due_date or invoice.posting_date),
		numero_socio=numero,
		dni=dni,
		socio_name=socio.name,
		socio_nombre=nombre,
		email=email,
	)


def _new_merchant_transaction_id(source: CheckoutSource) -> str:
	digest = hashlib.sha256(source.invoice_name.encode("utf-8")).hexdigest()[:26]
	return f"SIC-{digest}"


def _existing_merchant_transaction_id(source: CheckoutSource) -> str | None:
	rows = frappe.get_all(
		"Payment Log",
		filters={
			"provider": PROVIDER_SUPERVIELLE,
			"sales_invoice": source.invoice_name,
			"currency": "ARS",
		},
		fields=["merchant_transaction_id", "gateway_transaction_id", "amount"],
		order_by="creation desc",
		limit=5,
	)
	for row in rows:
		if (
			row.merchant_transaction_id
			and not row.gateway_transaction_id
			and abs(flt(row.amount) - flt(source.amount)) <= 0.005
		):
			return str(row.merchant_transaction_id)
	return None


def _sanitized_request(payload: dict[str, Any]) -> dict[str, Any]:
	return {key: value for key, value in payload.items() if key not in {"Hash", "Token", "AccessLink"}}


def _reject_log(log: Any, message: str) -> None:
	log.status = "Rechazado"
	log.error_message = str(message)[:2000]
	log.save(ignore_permissions=True)


def _post_json(url: str, payload: dict[str, Any], *, session: Any | None = None) -> Any:
	client = session or requests
	try:
		return client.post(url, json=payload, timeout=_TIMEOUT_SECONDS)
	except requests.RequestException as exc:
		raise SupervielleIntegrationError("No se pudo conectar con Supervielle.") from exc


def publicar_boton_pago(
	sales_invoice_name: str,
	*,
	session: Any | None = None,
) -> BotonPagoResult:
	settings = get_runtime_settings()
	source = _load_checkout_source(sales_invoice_name)
	merchant_id = _existing_merchant_transaction_id(source) or _new_merchant_transaction_id(source)
	base_payload = build_checkout_payload(source, settings, merchant_id)
	signed_payload = sign_payload(base_payload, settings.secret_key)
	log = record_gateway_transaction(
		merchant_transaction_id=merchant_id,
		provider=PROVIDER_SUPERVIELLE,
		gateway_reference=source.invoice_name,
		status="Recibido",
		amount=source.amount,
		currency="ARS",
		sales_invoice=source.invoice_name,
		socio=source.socio_name,
		payload=_sanitized_request(signed_payload),
		ignore_permissions=True,
	)
	if log.status != "Recibido":
		log.status = "Recibido"
		log.save(ignore_permissions=True)
	try:
		response = _post_json(settings.api_url, signed_payload, session=session)
		if int(response.status_code) < 200 or int(response.status_code) >= 300:
			raise SupervielleIntegrationError(
				f"Supervielle respondió HTTP {response.status_code}."
			)
		try:
			data = response.json()
		except (TypeError, ValueError) as exc:
			raise SupervielleIntegrationError("Supervielle devolvió JSON inválido.") from exc
		if not isinstance(data, dict):
			raise SupervielleIntegrationError("Respuesta Supervielle inválida.")
		validate_response_hash(data, settings.secret_key)
		url, token = extract_boton_pago_result(data, sandbox_mode=settings.sandbox_mode)
	except Exception as exc:
		_reject_log(log, str(exc))
		if isinstance(exc, SupervielleIntegrationError):
			raise
		raise SupervielleIntegrationError("Falló la publicación en Supervielle.") from exc
	return BotonPagoResult(url=url, transaction_id=merchant_id, response={"status": "ok"})


def _ensure_publish_permission(sales_invoice_name: str) -> None:
	if not _ALLOWED_ROLES.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado para publicar cobros"), frappe.PermissionError)
	if not frappe.has_permission("Sales Invoice", ptype="read", doc=sales_invoice_name):
		frappe.throw(_("Sin permiso sobre la factura"), frappe.PermissionError)


@frappe.whitelist()
def publicar_boton_pago_factura(sales_invoice_name: str) -> dict[str, Any]:
	_ensure_publish_permission(sales_invoice_name)
	result = publicar_boton_pago(sales_invoice_name)
	return {"url": result.url, "transaction_id": result.transaction_id}
