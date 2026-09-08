"""Cliente HTTP Botón de Pago Supervielle Cobranza Ágil."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from club_management.finance.permissions import ensure_finance_panel_access
from club_management.finance.services.payment_log import record_gateway_transaction
from club_management.integrations.supervielle.payload import (
	CheckoutSource,
	SupervielleRuntimeSettings,
	assert_sandbox_url_matches_mode,
	build_checkout_payload,
	extract_boton_pago_result,
	sign_payload,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.members.services.cobranza_manual import _campo_socio_en

try:
	import requests
except Exception:  # pragma: no cover
	requests = None  # type: ignore[assignment]

PROVIDER = "Banco Supervielle"
DEFAULT_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class BotonPagoResult:
	url: str | None
	transaction_id: str
	raw: dict[str, Any]
	payment_log: str | None


def load_runtime_settings() -> SupervielleRuntimeSettings:
	settings = frappe.get_single("Supervielle Settings")
	secret = settings.get_password("secret_key") if settings.secret_key else ""
	if not secret:
		raise SupervielleIntegrationError("Falta secret_key en Supervielle Settings.")
	api_url = (settings.api_url or "").strip()
	if not api_url:
		raise SupervielleIntegrationError("Falta api_url en Supervielle Settings.")
	return SupervielleRuntimeSettings(
		sandbox_mode=bool(int(settings.sandbox_mode or 0)),
		secret_key=secret,
		cuit_emisor=settings.cuit_emisor or "",
		api_url=api_url,
		concepto_default=settings.concepto_default or "PRUEBA",
	)


def _socio_nombre_visible(socio: Any) -> str:
	completo = (socio.get("nombre_completo") or "").strip()
	if completo:
		return completo
	parts = [str(socio.get("apellido") or "").strip(), str(socio.get("nombre") or "").strip()]
	return " ".join(p for p in parts if p)


def checkout_source_from_invoice(sales_invoice: str) -> CheckoutSource:
	invoice = frappe.get_doc("Sales Invoice", sales_invoice)
	if int(invoice.docstatus or 0) != 1:
		frappe.throw(_("La factura debe estar submitted para publicar el botón de pago."), frappe.ValidationError)

	amount = flt(invoice.get("outstanding_amount"))
	if amount <= 0:
		frappe.throw(_("La factura no tiene saldo para publicar en Supervielle."), frappe.ValidationError)

	campo_socio = _campo_socio_en("Sales Invoice")
	socio_name = (invoice.get(campo_socio) if campo_socio else None) or invoice.get("socio")
	if not socio_name:
		frappe.throw(_("La factura no tiene Socio vinculado."), frappe.ValidationError)

	socio = frappe.get_doc("Socio", socio_name)
	due = invoice.get("due_date") or invoice.get("posting_date")
	return CheckoutSource(
		invoice_name=invoice.name,
		amount=float(amount),
		due_date=str(getdate(due)),
		numero_socio=str(socio.get("numero_socio") or socio.name),
		socio_name=socio.name,
		socio_nombre=_socio_nombre_visible(socio),
		email=str(socio.get("email") or ""),
		periodo_cobro=invoice.get("periodo_cobro") or invoice.get("custom_periodo_cobro"),
	)


def _audit_payload(request_body: dict[str, Any], response_body: Any, http_status: int | None) -> dict[str, Any]:
	safe_request = dict(request_body)
	safe_request.pop("Hash", None)
	safe_request.pop("hash", None)
	return {
		"request": safe_request,
		"response": response_body,
		"http_status": http_status,
	}


def _record_attempt(
	*,
	transaction_id: str,
	invoice_name: str,
	socio_name: str,
	amount: float,
	payload: dict[str, Any],
	status: str,
) -> str:
	doc = record_gateway_transaction(
		gateway_transaction_id=transaction_id,
		provider=PROVIDER,
		gateway_reference=invoice_name,
		sales_invoice=invoice_name,
		socio=socio_name,
		amount=amount,
		payload=payload,
		status=status,
		ignore_permissions=True,
	)
	return doc.name


def _post_publicacion(
	*,
	api_url: str,
	body: dict[str, Any],
	session: Any | None,
	timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any], str]:
	sess = session
	if sess is None:
		if requests is None:
			raise SupervielleIntegrationError(
				"Dependencia 'requests' no disponible para integrar con Supervielle."
			)
		sess = requests.Session()
	try:
		resp = sess.post(api_url, json=body, timeout=timeout)
	except Exception as exc:
		frappe.log_error(
			title="Supervielle API Error",
			message=json.dumps({"url": api_url, "exception": repr(exc)}, ensure_ascii=False),
		)
		raise SupervielleIntegrationError("Error de red al llamar a Supervielle.") from exc

	status_code = int(getattr(resp, "status_code", 0) or 0)
	text = getattr(resp, "text", "") or ""
	try:
		data = resp.json()
	except Exception:
		data = {"raw": text}
	if not isinstance(data, dict):
		data = {"raw": data}
	return status_code, data, text


def _is_business_error(data: dict[str, Any]) -> bool:
	if data.get("error") or data.get("errors") or data.get("error_code") or data.get("codigo_error"):
		return True
	codigo = data.get("CodigoResultado")
	if codigo is None:
		codigo = data.get("codigoResultado")
	if codigo is None:
		return False
	try:
		return int(codigo) != 0
	except (TypeError, ValueError):
		return str(codigo).strip() not in {"0", "OK", "ok"}


def publicar_boton_pago(sales_invoice: str, *, session: Any | None = None) -> BotonPagoResult:
	"""Publica la deuda de una Sales Invoice y registra Payment Log."""
	settings = load_runtime_settings()
	assert_sandbox_url_matches_mode(sandbox_mode=settings.sandbox_mode, api_url=settings.api_url)
	source = checkout_source_from_invoice(sales_invoice)
	unsigned = build_checkout_payload(source, settings)
	body = sign_payload(unsigned, settings.secret_key)

	status_code, data, _text = _post_publicacion(
		api_url=settings.api_url,
		body=body,
		session=session,
	)
	audit = _audit_payload(body, data, status_code)

	if status_code != 200 or _is_business_error(data):
		attempt_id = f"PUB-{source.invoice_name}-{uuid.uuid4().hex[:12]}"
		_record_attempt(
			transaction_id=attempt_id,
			invoice_name=source.invoice_name,
			socio_name=source.socio_name,
			amount=source.amount,
			payload=audit,
			status="Rechazado",
		)
		frappe.log_error(
			title="Supervielle API Error",
			message=json.dumps({"url": settings.api_url, "status_code": status_code, "response": data}, ensure_ascii=False),
		)
		raise SupervielleIntegrationError(
			f"Supervielle respondió HTTP {status_code or 'desconocido'}."
		)

	try:
		url, bank_id = extract_boton_pago_result(data)
	except SupervielleIntegrationError:
		attempt_id = f"PUB-{source.invoice_name}-{uuid.uuid4().hex[:12]}"
		_record_attempt(
			transaction_id=attempt_id,
			invoice_name=source.invoice_name,
			socio_name=source.socio_name,
			amount=source.amount,
			payload=audit,
			status="Rechazado",
		)
		raise

	transaction_id = bank_id or f"PUB-{source.invoice_name}-{uuid.uuid4().hex[:12]}"
	log_name = _record_attempt(
		transaction_id=transaction_id,
		invoice_name=source.invoice_name,
		socio_name=source.socio_name,
		amount=source.amount,
		payload=audit,
		status="Recibido",
	)
	return BotonPagoResult(
		url=url,
		transaction_id=transaction_id,
		raw=data,
		payment_log=log_name,
	)


@frappe.whitelist()
def publicar_boton_pago_factura(sales_invoice: str) -> dict[str, Any]:
	"""Publica botón de pago para una factura. Requiere panel Finanzas + lectura SI."""
	ensure_finance_panel_access()
	if not sales_invoice:
		frappe.throw(_("Falta Sales Invoice"), frappe.ValidationError)
	if not frappe.has_permission("Sales Invoice", ptype="read", doc=sales_invoice):
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	result = publicar_boton_pago(sales_invoice)
	return {
		"url": result.url,
		"transaction_id": result.transaction_id,
		"payment_log": result.payment_log,
	}
