"""Helpers puros del payload Botón de Pago Supervielle (sin I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from urllib.parse import urlparse

from club_management.integrations.supervielle_api import SupervielleAPI, SupervielleIntegrationError

SANDBOX_API_HOST = "cobranzaagiltst.supervielle.com.ar"
SANDBOX_API_URL = f"https://{SANDBOX_API_HOST}/rest/botonpago/publicacion"
SANDBOX_CUIT = "20406381928"
SANDBOX_CONCEPTO = "PRUEBA"

PAYLOAD_KEY_ORDER = (
	"Cuit",
	"Concepto",
	"IdCliente",
	"IdReferencia",
	"Importe",
	"Moneda",
	"FechaVencimiento",
	"Email",
	"Nombre",
)

URL_RESPONSE_KEYS = (
	"UrlBotonPago",
	"urlBotonPago",
	"UrlPago",
	"urlPago",
	"Url",
	"url",
	"LinkPago",
	"linkPago",
	"Link",
	"link",
)

ID_RESPONSE_KEYS = (
	"IdTransaccion",
	"idTransaccion",
	"IdOperacion",
	"idOperacion",
	"CodigoTransaccion",
	"codigoTransaccion",
	"Id",
	"id",
	"Codigo",
	"codigo",
)


@dataclass(frozen=True)
class CheckoutSource:
	invoice_name: str
	amount: float
	due_date: str
	numero_socio: str
	socio_name: str
	socio_nombre: str
	email: str
	periodo_cobro: str | None = None


@dataclass(frozen=True)
class SupervielleRuntimeSettings:
	sandbox_mode: bool
	secret_key: str
	cuit_emisor: str
	api_url: str
	concepto_default: str


def digits_only(value: str | None) -> str:
	return "".join(ch for ch in (value or "") if ch.isdigit())


def format_importe(amount: float | int | str) -> str:
	quantized = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	return f"{quantized:.2f}"


def build_checkout_payload(
	source: CheckoutSource,
	settings: SupervielleRuntimeSettings,
) -> dict[str, str]:
	values = {
		"Cuit": digits_only(settings.cuit_emisor),
		"Concepto": (settings.concepto_default or SANDBOX_CONCEPTO).strip() or SANDBOX_CONCEPTO,
		"IdCliente": str(source.numero_socio).strip(),
		"IdReferencia": source.invoice_name,
		"Importe": format_importe(source.amount),
		"Moneda": "ARS",
		"FechaVencimiento": source.due_date,
		"Email": (source.email or "").strip(),
		"Nombre": (source.socio_nombre or "").strip(),
	}
	return {key: values[key] for key in PAYLOAD_KEY_ORDER}


def sign_payload(payload: dict[str, Any], secret_key: str) -> dict[str, Any]:
	api = SupervielleAPI(secret_key=secret_key)
	signed = api._prepare_payload(payload)
	hash_value = signed.pop("hash", None)
	if hash_value is None:
		raise SupervielleIntegrationError("No se pudo firmar el payload.")
	signed["Hash"] = hash_value
	return signed


def assert_sandbox_url_matches_mode(*, sandbox_mode: bool, api_url: str) -> None:
	host = (urlparse(api_url).hostname or "").lower()
	if sandbox_mode:
		if host != SANDBOX_API_HOST:
			raise SupervielleIntegrationError(
				"sandbox_mode está activo: api_url debe apuntar al host de test de Cobranza Ágil."
			)
		return
	if host == SANDBOX_API_HOST:
		raise SupervielleIntegrationError(
			"sandbox_mode está desactivado: no se puede publicar contra el host de test."
		)


def extract_boton_pago_result(data: dict[str, Any]) -> tuple[str | None, str]:
	url: str | None = None
	for key in URL_RESPONSE_KEYS:
		value = data.get(key)
		if isinstance(value, str) and value.strip():
			url = value.strip()
			break
	tid = ""
	for key in ID_RESPONSE_KEYS:
		value = data.get(key)
		if value is not None and str(value).strip():
			tid = str(value).strip()
			break
	if not url and not tid:
		raise SupervielleIntegrationError(
			"Supervielle no devolvió URL ni identificador de botón de pago."
		)
	return url, tid
