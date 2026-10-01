"""Consulta, tick de scheduler y auditoría de rendiciones Supervielle v6.2."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any, Iterable

import frappe
import requests
from frappe import _
from frappe.utils import now_datetime

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
VERIFICATION_ERROR_RESULT = "Error de Verificación"
_VERIFICATION_STATUS_CODE = "HASH"
_LOGGER_NAME = "supervielle.renditions"


@dataclass(frozen=True)
class HashVerificationResult:
	ok: bool
	expected: str
	received: str
	strict: bool


def _stringify_hash_value(value: Any) -> str:
	if value is None:
		return ""
	if isinstance(value, bool):
		return "true" if value else "false"
	return str(value)


def _iter_nested_hash_values(obj: Any) -> Iterable[str]:
	"""DFS de valores escalares; omite claves Hash/hash (vector provisional)."""
	if isinstance(obj, dict):
		for key, value in obj.items():
			if str(key).lower() == "hash":
				continue
			yield from _iter_nested_hash_values(value)
		return
	if isinstance(obj, (list, tuple)):
		for item in obj:
			yield from _iter_nested_hash_values(item)
		return
	yield _stringify_hash_value(obj)


def compute_nested_response_hash(data: dict[str, Any], secret_key: str) -> str:
	raw = "".join(_iter_nested_hash_values(data)) + (secret_key or "")
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_rendition_response_hash(
	data: dict[str, Any],
	secret_key: str,
	*,
	strict: bool = True,
) -> HashVerificationResult:
	"""Verificador criptográfico desacoplado; en no-strict no aborta."""
	if not isinstance(data, dict):
		raise SupervielleIntegrationError("Respuesta de rendiciones inválida.")
	received = str(data.get("Hash") or data.get("hash") or "").strip().lower()
	expected = compute_nested_response_hash(data, secret_key)
	ok = bool(received) and hmac.compare_digest(expected, received)
	result = HashVerificationResult(
		ok=ok,
		expected=expected,
		received=received,
		strict=strict,
	)
	if ok:
		return result
	if strict:
		raise SupervielleIntegrationError("Hash de respuesta de rendición inválido.")
	return result


def _extract_ids_from_rendition_payload(data: dict[str, Any]) -> tuple[str, str]:
	merchant_id = ""
	gateway_id = ""
	for rendition in data.get("rendiciones") or []:
		if not isinstance(rendition, dict):
			continue
		for doc in rendition.get("Documentos") or []:
			if not isinstance(doc, dict):
				continue
			if not merchant_id:
				merchant_id = str(doc.get("Libre1") or "").strip()
			if not gateway_id:
				gateway_id = str(doc.get("IdPago") or "").strip()
			if merchant_id and gateway_id:
				return merchant_id, gateway_id
	return merchant_id, gateway_id


def _sanitize_payload_for_event(data: dict[str, Any]) -> dict[str, Any]:
	"""Copia el payload omitiendo Hash/hash en cualquier nivel."""

	def _walk(obj: Any) -> Any:
		if isinstance(obj, dict):
			return {
				key: _walk(value)
				for key, value in obj.items()
				if str(key).lower() != "hash"
			}
		if isinstance(obj, list):
			return [_walk(item) for item in obj]
		return obj

	return _walk(data)


def _event_key_for_hash_failure(
	*,
	merchant_id: str,
	gateway_id: str,
	received: str,
) -> str:
	identity = "|".join(
		[
			PROVIDER_SUPERVIELLE,
			"HASH_FAIL",
			merchant_id,
			gateway_id,
			received,
		]
	)
	return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _event_key_for_raw_payload(snapshot: dict[str, Any], *, result: str) -> str:
	digest = hashlib.sha256(
		frappe.as_json(snapshot).encode("utf-8")
	).hexdigest()
	identity = "|".join([PROVIDER_SUPERVIELLE, "RENDITION_RAW", result, digest])
	return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _insert_gateway_event(
	*,
	event_key: str,
	merchant_id: str,
	gateway_id: str,
	status_code: str,
	status_description: str,
	result: str,
	snapshot: dict[str, Any],
	payment_log: str | None = None,
) -> str:
	existing = frappe.db.get_value("Payment Gateway Event", {"event_key": event_key}, "name")
	if existing:
		return existing
	if not payment_log:
		payment_log = frappe.db.get_value(
			"Payment Log",
			{"merchant_transaction_id": merchant_id},
			"name",
		)
	doc = frappe.get_doc(
		{
			"doctype": "Payment Gateway Event",
			"event_key": event_key,
			"provider": PROVIDER_SUPERVIELLE,
			"merchant_transaction_id": merchant_id,
			"gateway_transaction_id": gateway_id,
			"status_code": status_code,
			"status_description": status_description,
			"state_changed_at": now_datetime(),
			"payment_log": payment_log,
			"processing_result": result,
			"event_payload_json": frappe.as_json(snapshot),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def record_rendition_hash_verification_error(
	data: dict[str, Any],
	verification: HashVerificationResult,
) -> str | None:
	"""Persiste auditoría de discrepancia sin detener el flujo."""
	merchant_id, gateway_id = _extract_ids_from_rendition_payload(data)
	if not merchant_id:
		merchant_id = "RENDITION-HASH-AUDIT"
	if not gateway_id:
		gateway_id = f"HASH-{verification.received[:16] or 'missing'}"
	event_key = _event_key_for_hash_failure(
		merchant_id=merchant_id,
		gateway_id=gateway_id,
		received=verification.received,
	)
	snapshot = _sanitize_payload_for_event(data)
	frappe.logger(_LOGGER_NAME).warning(
		{
			"event": "rendition_hash_mismatch",
			"merchant_transaction_id": merchant_id,
			"gateway_transaction_id": gateway_id,
			"strict": verification.strict,
			"received_hash_prefix": (verification.received or "")[:12],
		}
	)
	return _insert_gateway_event(
		event_key=event_key,
		merchant_id=merchant_id,
		gateway_id=gateway_id,
		status_code=_VERIFICATION_STATUS_CODE,
		status_description=VERIFICATION_ERROR_RESULT,
		result=VERIFICATION_ERROR_RESULT,
		snapshot=snapshot,
	)


def persist_rendition_raw_event(
	data: dict[str, Any],
	*,
	result: str,
	hash_verified: bool,
) -> str:
	"""Persiste payload crudo sanitizado con clave idempotente ante reintentos."""
	merchant_id, gateway_id = _extract_ids_from_rendition_payload(data)
	if not merchant_id:
		merchant_id = "RENDITION-RAW"
	if not gateway_id:
		gateway_id = "RENDITION-BATCH"
	snapshot = _sanitize_payload_for_event(data)
	snapshot["_meta"] = {"hash_verified": bool(hash_verified)}
	event_key = _event_key_for_raw_payload(snapshot, result=result)
	return _insert_gateway_event(
		event_key=event_key,
		merchant_id=merchant_id,
		gateway_id=gateway_id,
		status_code="RAW",
		status_description=result,
		result=result,
		snapshot=snapshot,
	)


def process_renditions_response(
	data: dict[str, Any],
	*,
	secret_key: str,
	sandbox_mode: bool,
) -> dict[str, Any]:
	"""Verifica hash (strict según sandbox) y parsea preview."""
	strict = not bool(sandbox_mode)
	verification = verify_rendition_response_hash(data, secret_key, strict=strict)
	event_name = None
	if not verification.ok:
		# Solo alcanzable en modo auditoría (sandbox): strict ya habría lanzado.
		event_name = record_rendition_hash_verification_error(data, verification)
	else:
		event_name = persist_rendition_raw_event(
			data,
			result="audited",
			hash_verified=True,
		)
	return {
		"mode": "preview",
		"hash_verified": verification.ok,
		"automatic_apply": False,
		"verification_event": event_name,
		"rows": parse_renditions_preview(data),
	}


def _read_polling_flags() -> tuple[bool, bool]:
	"""Lee sandbox_mode y polling_enabled sin exigir secret_key."""
	sandbox = bool(frappe.db.get_single_value("Supervielle Settings", "sandbox_mode"))
	polling = bool(frappe.db.get_single_value("Supervielle Settings", "polling_enabled"))
	return sandbox, polling


def _resolve_tick_credentials() -> tuple[str, bool]:
	from club_management.integrations.supervielle.client import get_runtime_settings

	settings = get_runtime_settings()
	return settings.secret_key, bool(settings.sandbox_mode)


def is_rendition_polling_active(*, sandbox_mode: bool, polling_enabled: bool) -> bool:
	return bool(sandbox_mode or polling_enabled)


def fetch_renditions_raw(
	*,
	filters: dict[str, Any] | None = None,
	session: Any | None = None,
) -> dict[str, Any]:
	"""POST a /rest/rendicion y devuelve el JSON crudo."""
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
	if not isinstance(data, dict):
		raise SupervielleIntegrationError("Respuesta de rendiciones inválida.")
	return data


def process_renditions_scheduler_tick(
	payloads: list[dict[str, Any]] | None = None,
	*,
	secret_key: str | None = None,
	sandbox_mode: bool | None = None,
	polling_enabled: bool | None = None,
	session: Any | None = None,
) -> list[dict[str, Any]]:
	"""Job de lote: consulta pendientes si el polling está activo y procesa.

	Si `payloads` viene informado (tests / reproceso), no consulta la API.
	En sandbox el hash se valida en modo auditoría (`strict=False`).
	"""
	if payloads is None:
		flags_sandbox, flags_polling = _read_polling_flags()
		active_sandbox = flags_sandbox if sandbox_mode is None else bool(sandbox_mode)
		active_polling = flags_polling if polling_enabled is None else bool(polling_enabled)
		if not is_rendition_polling_active(
			sandbox_mode=active_sandbox,
			polling_enabled=active_polling,
		):
			return []
		raw = fetch_renditions_raw(session=session)
		payloads = [raw]
		if secret_key is None or sandbox_mode is None:
			resolved_secret, resolved_sandbox = _resolve_tick_credentials()
			secret_key = secret_key or resolved_secret
			sandbox_mode = resolved_sandbox if sandbox_mode is None else sandbox_mode
	elif secret_key is None or sandbox_mode is None:
		raise SupervielleIntegrationError(
			"secret_key y sandbox_mode son obligatorios al reprocesar payloads."
		)

	assert secret_key is not None and sandbox_mode is not None
	outcomes: list[dict[str, Any]] = []
	for data in payloads:
		outcomes.append(
			process_renditions_response(
				data,
				secret_key=secret_key,
				sandbox_mode=sandbox_mode,
			)
		)
	return outcomes


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
	data = fetch_renditions_raw(filters=filters, session=session)
	return process_renditions_response(
		data,
		secret_key=settings.secret_key,
		sandbox_mode=settings.sandbox_mode,
	)


@frappe.whitelist()
def preview_renditions(filters: dict[str, Any] | None = None) -> dict[str, Any]:
	if not {"System Manager", "Tesoreria"}.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado para consultar rendiciones"), frappe.PermissionError)
	return fetch_renditions_preview(filters=filters)
