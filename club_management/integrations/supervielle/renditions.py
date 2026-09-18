"""Consulta en modo preview de rendiciones Supervielle v6.2."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

import frappe
import requests
from frappe import _

from club_management.finance.services.payment_log import PROVIDER_SUPERVIELLE
from club_management.integrations.supervielle.payload import (
	assert_sandbox_url_matches_mode,
	digits_only,
	sign_payload,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError

RENDITION_REQUEST_FIELDS = (
	"IdEmpresa",
	"Convenio",
	"IdRendicionDesde",
	"IdRendicionHasta",
	"IdInstrumentoDesde",
	"IdInstrumentoHasta",
	"FechaRendicionDesde",
	"FechaRendicionHasta",
	"FechaPagoDesde",
	"FechaPagoHasta",
	"FechaCambioEstadoDesde",
	"FechaCambioEstadoHasta",
	"CUITCliente",
	"NroCliente",
	"ImpPagoDesde",
	"ImpPagoHasta",
	"InfoDocumentos",
	"InfoRetenciones",
	"InfoDisputas",
	"FechaPagoInstrumentoDesde",
	"FechaPagoInstrumentoHasta",
)
_TIMEOUT_SECONDS = 30
_POLL_MERCHANT_ID = "RENDITION-POLL"
_POLL_GATEWAY_ID = "RENDITION-POLL-ERROR"
_POLL_ERROR_RESULT = "poll_error"
_SEVERITY_HIGH = "High"


def build_rendition_request(
	*,
	id_empresa: str,
	convenio: str,
	secret_key: str,
	filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
	values: dict[str, Any] = {
		"IdEmpresa": digits_only(id_empresa),
		"Convenio": convenio or "TODOS",
		"IdRendicionDesde": "0",
		"IdRendicionHasta": "999999999",
		"IdInstrumentoDesde": "0",
		"IdInstrumentoHasta": "999999999",
		"FechaRendicionDesde": "",
		"FechaRendicionHasta": "",
		"FechaPagoDesde": "",
		"FechaPagoHasta": "",
		"FechaCambioEstadoDesde": "",
		"FechaCambioEstadoHasta": "",
		"CUITCliente": "",
		"NroCliente": "",
		"ImpPagoDesde": "",
		"ImpPagoHasta": "",
		"InfoDocumentos": "S",
		"InfoRetenciones": "S",
		"InfoDisputas": "S",
		"FechaPagoInstrumentoDesde": "",
		"FechaPagoInstrumentoHasta": "",
	}
	for key, value in (filters or {}).items():
		if key not in values:
			raise SupervielleIntegrationError(f"Filtro de rendición no permitido: {key}.")
		values[key] = value
	ordered = {key: values[key] for key in RENDITION_REQUEST_FIELDS}
	return sign_payload(ordered, secret_key)


def parse_renditions_preview(data: dict[str, Any]) -> list[dict[str, Any]]:
	renditions = data.get("rendiciones") or []
	if not isinstance(renditions, list):
		raise SupervielleIntegrationError("Respuesta de rendiciones inválida.")
	rows: list[dict[str, Any]] = []
	seen: set[tuple[str, str]] = set()
	for rendition in renditions:
		if not isinstance(rendition, dict):
			continue
		documents = rendition.get("Documentos") or []
		merchant_ids = {
			str(doc.get("Libre1") or "").strip()
			for doc in documents
			if isinstance(doc, dict) and str(doc.get("Libre1") or "").strip()
		}
		portal_ids = {
			str(doc.get("IdPago") or "").strip()
			for doc in documents
			if isinstance(doc, dict) and str(doc.get("IdPago") or "").strip()
		}
		merchant_id = next(iter(merchant_ids)) if len(merchant_ids) == 1 else ""
		portal_id = next(iter(portal_ids)) if len(portal_ids) == 1 else ""
		for instrument in rendition.get("Instrumentos") or []:
			if not isinstance(instrument, dict):
				continue
			identity = (
				str(rendition.get("idRendicion") or ""),
				str(instrument.get("idInstrumento") or ""),
			)
			if identity in seen:
				continue
			seen.add(identity)
			state = str(instrument.get("codigoEstado") or "").strip()
			rows.append(
				{
					"rendition_id": identity[0],
					"instrument_id": identity[1],
					"state": state,
					"amount": instrument.get("importe"),
					"currency": rendition.get("codigoMoneda") or "ARS",
					"merchant_transaction_id": merchant_id,
					"gateway_transaction_id": portal_id,
					"candidate_for_reconciliation": bool(
						state == "AC" and merchant_id and portal_id
					),
					"automatic_apply": False,
				}
			)
	return rows


def fetch_renditions_preview(
	*,
	filters: dict[str, Any] | None = None,
	session: Any | None = None,
) -> dict[str, Any]:
	from club_management.integrations.supervielle.client import get_runtime_settings

	settings = get_runtime_settings()
	assert_sandbox_url_matches_mode(
		sandbox_mode=settings.sandbox_mode,
		api_url=settings.rendicion_api_url,
	)
	payload = build_rendition_request(
		id_empresa=settings.cuit_emisor,
		convenio=settings.convenio,
		secret_key=settings.secret_key,
		filters=filters,
	)
	client = session or requests
	try:
		response = client.post(
			settings.rendicion_api_url,
			json=payload,
			timeout=_TIMEOUT_SECONDS,
		)
	except requests.RequestException as exc:
		raise SupervielleIntegrationError("No se pudo consultar rendiciones.") from exc
	if not 200 <= int(response.status_code) < 300:
		raise SupervielleIntegrationError(f"Supervielle respondió HTTP {response.status_code}.")
	try:
		data = response.json()
	except (TypeError, ValueError) as exc:
		raise SupervielleIntegrationError("Rendiciones devolvió JSON inválido.") from exc
	return {
		"mode": "preview",
		"hash_verified": False,
		"automatic_apply": False,
		"rows": parse_renditions_preview(data),
	}


@frappe.whitelist()
def preview_renditions(filters: dict[str, Any] | None = None) -> dict[str, Any]:
	if not {"System Manager", "Tesoreria"}.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado para consultar rendiciones"), frappe.PermissionError)
	return fetch_renditions_preview(filters=filters)


def _polling_enabled() -> bool:
	return bool(frappe.db.get_single_value("Supervielle Settings", "enable_automated_polling"))


def _record_polling_failure(exc: BaseException) -> str | None:
	"""Audita timeout/HTTP de Cobrand sin secretos ni Hash."""
	occurred_at = datetime.now()
	snapshot = {
		"error": type(exc).__name__,
		"message": str(exc)[:500],
	}
	identity = "|".join(
		[
			PROVIDER_SUPERVIELLE,
			_POLL_MERCHANT_ID,
			_POLL_ERROR_RESULT,
			str(occurred_at),
			snapshot["error"],
			snapshot["message"],
		]
	)
	event_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
	try:
		existing = frappe.db.get_value("Payment Gateway Event", {"event_key": event_key}, "name")
		if existing:
			return str(existing)
		doc = frappe.get_doc(
			{
				"doctype": "Payment Gateway Event",
				"event_key": event_key,
				"provider": PROVIDER_SUPERVIELLE,
				"merchant_transaction_id": _POLL_MERCHANT_ID,
				"gateway_transaction_id": _POLL_GATEWAY_ID,
				"status_code": "POLL_ERROR",
				"status_description": str(exc)[:140],
				"state_changed_at": occurred_at,
				"processing_result": _POLL_ERROR_RESULT,
				"severity": _SEVERITY_HIGH,
				"event_payload_json": frappe.as_json(snapshot),
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name
	except Exception:
		frappe.log_error(
			title="Supervielle renditions poll",
			message=f"{type(exc).__name__}: {str(exc)[:500]}",
		)
		return None


def process_renditions_scheduler_tick(*, session: Any | None = None) -> dict[str, Any]:
	"""Job horario: consulta rendiciones si el polling está habilitado.

	Timeout o HTTP != 200 se registran en Payment Gateway Event (High)
	y no se re-lanzan, para no interrumpir la cola de Frappe.
	"""
	if not _polling_enabled():
		return {"skipped": True, "reason": "polling_disabled"}
	try:
		preview = fetch_renditions_preview(session=session)
		return {"skipped": False, "rows": preview.get("rows") or []}
	except Exception as exc:
		event_name = _record_polling_failure(exc)
		return {"skipped": False, "error": str(exc), "event": event_name}
