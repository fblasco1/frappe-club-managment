"""Tests unitarios del Botón de Pago Supervielle (spec supervielle_boton_pago.md)."""

from __future__ import annotations

import hashlib
import unittest
from unittest.mock import MagicMock

from club_management.integrations.supervielle.payload import (
	SANDBOX_API_HOST,
	SANDBOX_API_URL,
	SANDBOX_CONCEPTO,
	SANDBOX_CUIT,
	CheckoutSource,
	SupervielleRuntimeSettings,
	assert_sandbox_url_matches_mode,
	build_checkout_payload,
	extract_boton_pago_result,
	format_importe,
	sign_payload,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError


SANDBOX_SECRET = "14D6C372-F28C-4DED-BE02-71E3A6C94415"


def _source() -> CheckoutSource:
	return CheckoutSource(
		invoice_name="ACC-SINV-0001",
		amount=19500,
		due_date="2026-09-10",
		numero_socio="12062",
		socio_name="12062",
		socio_nombre="PEREZ ANA",
		email="ana@example.com",
		periodo_cobro="09/2026",
	)


def _settings(*, sandbox_mode: bool = True, api_url: str = SANDBOX_API_URL) -> SupervielleRuntimeSettings:
	return SupervielleRuntimeSettings(
		sandbox_mode=sandbox_mode,
		secret_key=SANDBOX_SECRET,
		cuit_emisor="20-40638192-8",
		api_url=api_url,
		concepto_default=SANDBOX_CONCEPTO,
	)


class TestSupervielleBotonPagoPayload(unittest.TestCase):
	def test_payload_order_and_sources(self) -> None:
		payload = build_checkout_payload(_source(), _settings())
		self.assertEqual(
			list(payload.keys()),
			[
				"Cuit",
				"Concepto",
				"IdCliente",
				"IdReferencia",
				"Importe",
				"Moneda",
				"FechaVencimiento",
				"Email",
				"Nombre",
			],
		)
		self.assertEqual(payload["Cuit"], SANDBOX_CUIT)
		self.assertEqual(payload["Concepto"], "PRUEBA")
		self.assertEqual(payload["IdCliente"], "12062")
		self.assertEqual(payload["IdReferencia"], "ACC-SINV-0001")
		self.assertEqual(payload["Importe"], "19500.00")
		self.assertEqual(payload["Moneda"], "ARS")
		self.assertEqual(payload["FechaVencimiento"], "2026-09-10")
		self.assertEqual(payload["Email"], "ana@example.com")
		self.assertEqual(payload["Nombre"], "PEREZ ANA")
		self.assertNotIn("Hash", payload)
		self.assertNotIn(SANDBOX_SECRET, str(payload))

	def test_sign_payload_excludes_hash_and_appends_secret(self) -> None:
		base = build_checkout_payload(_source(), _settings())
		signed = sign_payload(base, SANDBOX_SECRET)
		concatenated = (
			"".join(
				[
					SANDBOX_CUIT,
					"PRUEBA",
					"12062",
					"ACC-SINV-0001",
					"19500.00",
					"ARS",
					"2026-09-10",
					"ana@example.com",
					"PEREZ ANA",
				]
			)
			+ SANDBOX_SECRET
		)
		expected = hashlib.sha256(concatenated.encode("utf-8")).hexdigest()
		self.assertEqual(signed["Hash"], expected)
		self.assertEqual(expected, expected.lower())

	def test_format_importe_two_decimals(self) -> None:
		self.assertEqual(format_importe(19500), "19500.00")
		self.assertEqual(format_importe(19500.5), "19500.50")

	def test_sandbox_mode_rejects_production_host(self) -> None:
		prod = "https://cobranzaagil.supervielle.com.ar/rest/botonpago/publicacion"
		with self.assertRaises(SupervielleIntegrationError):
			assert_sandbox_url_matches_mode(sandbox_mode=True, api_url=prod)

	def test_production_mode_rejects_sandbox_host(self) -> None:
		with self.assertRaises(SupervielleIntegrationError):
			assert_sandbox_url_matches_mode(sandbox_mode=False, api_url=SANDBOX_API_URL)

	def test_sandbox_mode_allows_test_host(self) -> None:
		assert_sandbox_url_matches_mode(sandbox_mode=True, api_url=SANDBOX_API_URL)
		self.assertIn(SANDBOX_API_HOST, SANDBOX_API_URL)

	def test_extract_url_and_id_from_response(self) -> None:
		url, tid = extract_boton_pago_result(
			{"UrlBotonPago": "https://pago.example/abc", "IdTransaccion": "TX-99"}
		)
		self.assertEqual(url, "https://pago.example/abc")
		self.assertEqual(tid, "TX-99")

	def test_extract_id_without_url(self) -> None:
		url, tid = extract_boton_pago_result({"IdOperacion": "OP-1"})
		self.assertIsNone(url)
		self.assertEqual(tid, "OP-1")

	def test_extract_without_url_or_id_raises(self) -> None:
		with self.assertRaises(SupervielleIntegrationError):
			extract_boton_pago_result({"Mensaje": "ok"})
