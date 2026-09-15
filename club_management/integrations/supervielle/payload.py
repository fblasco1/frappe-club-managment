"""Contrato puro Botón de Pago Supervielle v2.6."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlparse

from frappe.utils import getdate

from club_management.integrations.supervielle_api import SupervielleIntegrationError

SANDBOX_API_HOST = "cobranzaagiltst.supervielle.com.ar"
PRODUCTION_API_HOST = "www.cobranzaagil.supervielle.com.ar"
SANDBOX_API_URL = f"https://{SANDBOX_API_HOST}/rest/botonpago/publicacion"
SANDBOX_RENDITION_URL = f"https://{SANDBOX_API_HOST}/rest/rendicion"
SANDBOX_CUIT = "20406381928"
SANDBOX_CONCEPTO = "PRUEBA"

PAYLOAD_KEY_ORDER = (
	"IdEmpresa",
	"UserName",
	"Nombre",
	"NroDoc",
	"Concepto",
	"Importe",
	"DatoLibreEmp",
	"URLOk",
	"URLError",
	"FechaVencPubl",
	"ImporteSegVenc",
	"FechaSegVencPubl",
)


@dataclass(frozen=True)
class CheckoutSource:
	invoice_name: str
	amount: float
	due_date: str
	numero_socio: str
	dni: str
	socio_name: str
	socio_nombre: str
	email: str


@dataclass(frozen=True)
class SupervielleRuntimeSettings:
	sandbox_mode: bool
	secret_key: str
	cuit_emisor: str
	api_url: str
	concepto_default: str
	url_ok: str
	url_error: str
	rendicion_api_url: str
	convenio: str
	mode_of_payment: str
	clearing_account: str


def digits_only(value: str | None) -> str:
	return "".join(ch for ch in (value or "") if ch.isdigit())


def format_importe(amount: float | int | str) -> str:
	quantized = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	return f"{quantized:.2f}"


def format_fecha(value: date | str | None) -> str:
	return getdate(value).strftime("%d%m%Y") if value else ""


def build_checkout_payload(
	source: CheckoutSource,
	settings: SupervielleRuntimeSettings,
	merchant_transaction_id: str,
) -> dict[str, str]:
	merchant_id = str(merchant_transaction_id or "").strip()
	if not merchant_id or len(merchant_id) > 30:
		raise SupervielleIntegrationError("DatoLibreEmp debe tener entre 1 y 30 caracteres.")
	concepto = str(settings.concepto_default or "").strip()
	if not concepto or len(concepto) > 10:
		raise SupervielleIntegrationError("Concepto debe tener entre 1 y 10 caracteres.")
	values = {
		"IdEmpresa": digits_only(settings.cuit_emisor),
		"UserName": str(source.email or "").strip(),
		"Nombre": str(source.socio_nombre or "").strip(),
		"NroDoc": digits_only(source.dni) or str(source.numero_socio).strip(),
		"Concepto": concepto,
		"Importe": format_importe(source.amount),
		"DatoLibreEmp": merchant_id,
		"URLOk": str(settings.url_ok or "").strip(),
		"URLError": str(settings.url_error or "").strip(),
		"FechaVencPubl": format_fecha(source.due_date),
		"ImporteSegVenc": "",
		"FechaSegVencPubl": "",
	}
	for required in ("IdEmpresa", "UserName", "Nombre", "NroDoc", "URLOk", "URLError"):
		if not values[required]:
			raise SupervielleIntegrationError(f"Falta campo obligatorio {required}.")
	return {key: values[key] for key in PAYLOAD_KEY_ORDER}


def _hash_values(values: list[Any], secret_key: str) -> str:
	raw = "".join(str(value or "") for value in values) + secret_key
	return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sign_payload(payload: dict[str, Any], secret_key: str) -> dict[str, Any]:
	signed = dict(payload)
	signed.pop("Hash", None)
	signed.pop("hash", None)
	signed["Hash"] = _hash_values(list(signed.values()), secret_key)
	return signed


def validate_response_hash(data: dict[str, Any], secret_key: str) -> None:
	token = str(data.get("Token") or "").strip()
	received = str(data.get("Hash") or "").strip().lower()
	if not token or not received:
		raise SupervielleIntegrationError("Respuesta Supervielle sin Token/Hash.")
	expected = _hash_values([token], secret_key)
	if not hmac.compare_digest(expected, received):
		raise SupervielleIntegrationError("Hash de respuesta Supervielle inválido.")


def assert_sandbox_url_matches_mode(*, sandbox_mode: bool, api_url: str) -> None:
	host = (urlparse(api_url).hostname or "").lower()
	if sandbox_mode and host != SANDBOX_API_HOST:
		raise SupervielleIntegrationError("sandbox_mode requiere el host QA de Cobranza Ágil.")
	if not sandbox_mode and host != PRODUCTION_API_HOST:
		raise SupervielleIntegrationError("Producción requiere el host productivo de Cobranza Ágil.")


def extract_boton_pago_result(
	data: dict[str, Any],
	*,
	sandbox_mode: bool,
) -> tuple[str, str]:
	token = str(data.get("Token") or "").strip()
	url = str(data.get("AccessLink") or "").strip()
	if not token or not url:
		raise SupervielleIntegrationError("Supervielle no devolvió Token/AccessLink.")
	parsed = urlparse(url)
	expected_host = SANDBOX_API_HOST if sandbox_mode else PRODUCTION_API_HOST
	if parsed.scheme != "https" or (parsed.hostname or "").lower() != expected_host:
		raise SupervielleIntegrationError("AccessLink fuera del host Supervielle permitido.")
	return url, token
