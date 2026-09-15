"""Contrato de consulta, tick e idempotencia de rendiciones Supervielle v6.2."""

from __future__ import annotations

import hashlib
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import frappe

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	record_gateway_transaction,
)
from club_management.integrations.supervielle.renditions import (
	VERIFICATION_ERROR_RESULT,
	build_rendition_request,
	compute_nested_response_hash,
	parse_renditions_preview,
	persist_rendition_raw_event,
	process_renditions_scheduler_tick,
	verify_rendition_response_hash,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.members.test_helpers import MembersTestCase

SECRET = "rendition-secret"


def _nested_payload(*, hash_value: str | None = "bad-hash") -> dict[str, Any]:
	body: dict[str, Any] = {
		"rendiciones": [
			{
				"idRendicion": 10,
				"codigoMoneda": "ARS",
				"Instrumentos": [
					{"idInstrumento": 20, "codigoEstado": "AC", "importe": "100,00"},
					{"idInstrumento": 21, "codigoEstado": "RC", "importe": "50,00"},
				],
				"Documentos": [{"IdPago": "PORTAL-HASH-1", "Libre1": "SIC-HASH-1"}],
			}
		]
	}
	if hash_value is not None:
		body["Hash"] = hash_value
	return body


class TestSupervielleRenditionsContract(unittest.TestCase):
	def test_request_completo_y_ordenado(self) -> None:
		payload = build_rendition_request(
			id_empresa="20406381928",
			convenio="TODOS",
			secret_key="secret",
		)
		self.assertEqual(
			list(payload)[:6],
			[
				"IdEmpresa",
				"Convenio",
				"IdRendicionDesde",
				"IdRendicionHasta",
				"IdInstrumentoDesde",
				"IdInstrumentoHasta",
			],
		)
		self.assertEqual(payload["InfoDocumentos"], "S")
		self.assertIn("Hash", payload)

	def test_preview_mapea_libre1_y_solo_ac_como_candidato(self) -> None:
		response = {
			"rendiciones": [
				{
					"idRendicion": 10,
					"codigoMoneda": "ARS",
					"Instrumentos": [
						{"idInstrumento": 20, "codigoEstado": "AC", "importe": "100,00"},
						{"idInstrumento": 21, "codigoEstado": "RC", "importe": "100,00"},
					],
					"Documentos": [{"IdPago": "PORTAL-1", "Libre1": "SIC-1"}],
				}
			]
		}
		rows = parse_renditions_preview(response)
		self.assertEqual(len(rows), 2)
		self.assertTrue(rows[0]["candidate_for_reconciliation"])
		self.assertFalse(rows[1]["candidate_for_reconciliation"])
		self.assertEqual(rows[0]["merchant_transaction_id"], "SIC-1")

	def test_hash_provisional_excluye_claves_hash_en_anidado(self) -> None:
		payload = _nested_payload(hash_value="ignored")
		expected = compute_nested_response_hash(payload, SECRET)
		raw = (
			"10"
			+ "ARS"
			+ "20"
			+ "AC"
			+ "100,00"
			+ "21"
			+ "RC"
			+ "50,00"
			+ "PORTAL-HASH-1"
			+ "SIC-HASH-1"
			+ SECRET
		)
		self.assertEqual(expected, hashlib.sha256(raw.encode("utf-8")).hexdigest())

	def test_verify_strict_rechaza_discrepancia(self) -> None:
		with self.assertRaises(SupervielleIntegrationError):
			verify_rendition_response_hash(
				_nested_payload(hash_value="bad"),
				SECRET,
				strict=True,
			)

	def test_verify_audit_no_lanza_con_discrepancia(self) -> None:
		result = verify_rendition_response_hash(
			_nested_payload(hash_value="bad"),
			SECRET,
			strict=False,
		)
		self.assertFalse(result.ok)
		self.assertEqual(result.received, "bad")


class TestRenditionsSchedulerTick(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Payment Gateway Event"):
			self.skipTest("Payment Gateway Event no migrado")
		record_gateway_transaction(
			merchant_transaction_id="SIC-HASH-1",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			ignore_permissions=True,
		)

	def test_scheduler_audit_registra_error_verificacion_sin_abortar(self) -> None:
		bad = _nested_payload(hash_value="deadbeef")
		good = _nested_payload(hash_value=None)
		good["rendiciones"][0]["idRendicion"] = 11
		good["rendiciones"][0]["Documentos"][0]["Libre1"] = "SIC-HASH-2"
		good["rendiciones"][0]["Documentos"][0]["IdPago"] = "PORTAL-HASH-2"
		good["Hash"] = compute_nested_response_hash(good, SECRET)
		record_gateway_transaction(
			merchant_transaction_id="SIC-HASH-2",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=50,
			currency="ARS",
			ignore_permissions=True,
		)

		with patch(
			"club_management.integrations.supervielle.renditions.frappe.logger"
		) as logger_factory:
			logger = MagicMock()
			logger_factory.return_value = logger
			outcomes = process_renditions_scheduler_tick(
				[bad, good],
				secret_key=SECRET,
				sandbox_mode=True,
			)

		self.assertEqual(len(outcomes), 2)
		self.assertFalse(outcomes[0]["hash_verified"])
		self.assertTrue(outcomes[1]["hash_verified"])
		self.assertFalse(outcomes[0]["automatic_apply"])
		self.assertFalse(outcomes[1]["automatic_apply"])
		self.assertEqual(len(outcomes[0]["rows"]), 2)
		self.assertEqual(len(outcomes[1]["rows"]), 2)
		logger.warning.assert_called()
		warning_payload = logger.warning.call_args[0][0]
		self.assertEqual(warning_payload["event"], "rendition_hash_mismatch")

		events = frappe.get_all(
			"Payment Gateway Event",
			filters={
				"provider": PROVIDER_SUPERVIELLE,
				"processing_result": VERIFICATION_ERROR_RESULT,
				"merchant_transaction_id": "SIC-HASH-1",
			},
			fields=["name", "status_description", "event_payload_json", "gateway_transaction_id"],
		)
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].status_description, VERIFICATION_ERROR_RESULT)
		self.assertEqual(events[0].gateway_transaction_id, "PORTAL-HASH-1")
		self.assertNotIn("Hash", events[0].event_payload_json)
		self.assertNotIn("deadbeef", events[0].event_payload_json)

	def test_scheduler_strict_aborta_en_discrepancia(self) -> None:
		with self.assertRaises(SupervielleIntegrationError):
			process_renditions_scheduler_tick(
				[_nested_payload(hash_value="bad")],
				secret_key=SECRET,
				sandbox_mode=False,
			)
		self.assertEqual(
			frappe.db.count(
				"Payment Gateway Event",
				{
					"processing_result": VERIFICATION_ERROR_RESULT,
					"merchant_transaction_id": "SIC-HASH-1",
				},
			),
			0,
		)

	def test_persistencia_raw_idempotente_ante_reintento(self) -> None:
		payload = _nested_payload(hash_value=None)
		payload["Hash"] = compute_nested_response_hash(payload, SECRET)
		first = persist_rendition_raw_event(
			payload,
			result="audited",
			hash_verified=True,
		)
		second = persist_rendition_raw_event(
			payload,
			result="audited",
			hash_verified=True,
		)
		self.assertEqual(first, second)
		self.assertEqual(
			frappe.db.count(
				"Payment Gateway Event",
				{"name": first},
			),
			1,
		)

	def test_tick_inactivo_sin_sandbox_ni_polling(self) -> None:
		with patch(
			"club_management.integrations.supervielle.renditions._read_polling_flags",
			return_value=(False, False),
		), patch(
			"club_management.integrations.supervielle.renditions.fetch_renditions_raw",
		) as fetch_raw:
			outcomes = process_renditions_scheduler_tick()
		self.assertEqual(outcomes, [])
		fetch_raw.assert_not_called()

	def test_tick_activo_por_polling_consulta_api(self) -> None:
		good = _nested_payload(hash_value=None)
		good["Hash"] = compute_nested_response_hash(good, SECRET)
		with patch(
			"club_management.integrations.supervielle.renditions._read_polling_flags",
			return_value=(False, True),
		), patch(
			"club_management.integrations.supervielle.renditions.fetch_renditions_raw",
			return_value=good,
		) as fetch_raw, patch(
			"club_management.integrations.supervielle.renditions._resolve_tick_credentials",
			return_value=(SECRET, False),
		):
			outcomes = process_renditions_scheduler_tick()
		fetch_raw.assert_called_once()
		self.assertEqual(len(outcomes), 1)
		self.assertTrue(outcomes[0]["hash_verified"])
