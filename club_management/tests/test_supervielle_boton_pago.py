"""Contrato puro Botón de Pago Supervielle v2.6."""

from __future__ import annotations

import hashlib
import unittest

from club_management.integrations.supervielle.payload import (
	SANDBOX_API_HOST,
	SANDBOX_API_URL,
	SANDBOX_CONCEPTO,
	CheckoutSource,
	SupervielleRuntimeSettings,
	assert_sandbox_url_matches_mode,
	build_checkout_payload,
	extract_boton_pago_result,
	format_importe,
	sign_payload,
	validate_response_hash,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError

SANDBOX_SECRET = "14D6C372-F28C-4DED-BE02-71E3A6C94415"


def _source() -> CheckoutSource:
	return CheckoutSource(
		invoice_name="ACC-SINV-0001",
		amount=19500,
		due_date="2026-09-10",
		numero_socio="12062",
		dni="23456789",
		socio_name="12062",
		socio_nombre="PEREZ ANA",
		email="ana@example.com",
	)


def _settings(*, sandbox_mode: bool = True, api_url: str = SANDBOX_API_URL) -> SupervielleRuntimeSettings:
	return SupervielleRuntimeSettings(
		sandbox_mode=sandbox_mode,
		secret_key=SANDBOX_SECRET,
		cuit_emisor="20-40638192-8",
		api_url=api_url,
		concepto_default=SANDBOX_CONCEPTO,
		url_ok="https://gestion.icdpedroechague.com.ar/pago-ok",
		url_error="https://gestion.icdpedroechague.com.ar/pago-error",
		rendicion_api_url="https://cobranzaagiltst.supervielle.com.ar/rest/rendicion",
		convenio="TODOS",
		mode_of_payment="Cobros Plus (ARS)",
		clearing_account="115002 Cobros Plus - a liquidar (ARS) - ICDPE",
	)


class TestSupervielleBotonPagoPayload(unittest.TestCase):
	def test_payload_v26_order_and_sources(self) -> None:
		payload = build_checkout_payload(_source(), _settings(), "SICLUB-ABC123")
		self.assertEqual(
			list(payload),
			[
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
			],
		)
		self.assertEqual(payload["IdEmpresa"], "20406381928")
		self.assertEqual(payload["NroDoc"], "23456789")
		self.assertEqual(payload["DatoLibreEmp"], "SICLUB-ABC123")
		self.assertEqual(payload["Importe"], "19500.00")
		self.assertEqual(payload["FechaVencPubl"], "10092026")
		self.assertEqual(payload["ImporteSegVenc"], "")
		self.assertNotIn(SANDBOX_SECRET, str(payload))

	def test_sign_payload_uses_values_in_order(self) -> None:
		base = build_checkout_payload(_source(), _settings(), "SICLUB-ABC123")
		signed = sign_payload(base, SANDBOX_SECRET)
		expected = hashlib.sha256(
			("".join(str(value) for value in base.values()) + SANDBOX_SECRET).encode("utf-8")
		).hexdigest()
		self.assertEqual(signed["Hash"], expected)

	def test_response_hash_and_access_link(self) -> None:
		token = "50bb6cd4-6579-4abf-b6cd-84bc56d86e51"
		response_hash = hashlib.sha256((token + SANDBOX_SECRET).encode("utf-8")).hexdigest()
		payload = {
			"Token": token,
			"Hash": response_hash,
			"AccessLink": "https://cobranzaagiltst.supervielle.com.ar/Clientes/Login?token=x",
		}
		validate_response_hash(payload, SANDBOX_SECRET)
		url, returned_token = extract_boton_pago_result(payload, sandbox_mode=True)
		self.assertEqual(returned_token, token)
		self.assertEqual(url, payload["AccessLink"])

	def test_response_hash_invalido_y_host_externo_fallan(self) -> None:
		with self.assertRaises(SupervielleIntegrationError):
			validate_response_hash({"Token": "x", "Hash": "bad"}, SANDBOX_SECRET)
		with self.assertRaises(SupervielleIntegrationError):
			extract_boton_pago_result(
				{"Token": "x", "AccessLink": "https://attacker.example/token"},
				sandbox_mode=True,
			)

	def test_format_importe_two_decimals(self) -> None:
		self.assertEqual(format_importe(19500.5), "19500.50")

	def test_ambiente_cruzado_falla(self) -> None:
		prod = "https://www.cobranzaagil.supervielle.com.ar/rest/botonpago/publicacion"
		with self.assertRaises(SupervielleIntegrationError):
			assert_sandbox_url_matches_mode(sandbox_mode=True, api_url=prod)
		with self.assertRaises(SupervielleIntegrationError):
			assert_sandbox_url_matches_mode(sandbox_mode=False, api_url=SANDBOX_API_URL)
		self.assertIn(SANDBOX_API_HOST, SANDBOX_API_URL)
