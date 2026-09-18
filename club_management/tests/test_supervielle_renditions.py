"""Contrato de consulta, preview y tick horario de rendiciones Supervielle v6.2."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import requests

from club_management.integrations.supervielle.payload import (
	SANDBOX_API_URL,
	SANDBOX_RENDITION_URL,
	SupervielleRuntimeSettings,
)
from club_management.integrations.supervielle.renditions import (
	build_rendition_request,
	parse_renditions_preview,
	process_renditions_scheduler_tick,
)


def _sandbox_settings() -> SupervielleRuntimeSettings:
	return SupervielleRuntimeSettings(
		sandbox_mode=True,
		secret_key="secret",
		cuit_emisor="20406381928",
		api_url=SANDBOX_API_URL,
		concepto_default="PRUEBA",
		url_ok="https://example.com/ok",
		url_error="https://example.com/error",
		rendicion_api_url=SANDBOX_RENDITION_URL,
		convenio="TODOS",
		mode_of_payment="Cash",
		clearing_account="Debtors - T",
	)


def _ok_response() -> MagicMock:
	response = MagicMock()
	response.status_code = 200
	response.json.return_value = {
		"rendiciones": [
			{
				"idRendicion": 10,
				"codigoMoneda": "ARS",
				"Instrumentos": [
					{"idInstrumento": 20, "codigoEstado": "AC", "importe": "100,00"},
				],
				"Documentos": [{"IdPago": "PORTAL-1", "Libre1": "SIC-1"}],
			}
		]
	}
	return response


class _CapturingDoc:
	payloads: list[dict[str, Any]] = []

	def __init__(self, payload: Any, name: Any | None = None) -> None:
		if isinstance(payload, dict):
			self.payload = payload
			_CapturingDoc.payloads.append(payload)
			self.name = "PGE-MOCK"
			return
		self.payload = {"doctype": payload, "name": name}
		self.name = str(name or payload)

	def insert(self, ignore_permissions: bool = False) -> "_CapturingDoc":
		return self


class TestSupervielleRenditions(unittest.TestCase):
	def test_request_completo_y_ordenado(self) -> None:
		payload = build_rendition_request(
			id_empresa="20406381928",
			convenio="TODOS",
			secret_key="secret",
		)
		self.assertEqual(list(payload)[:6], [
			"IdEmpresa",
			"Convenio",
			"IdRendicionDesde",
			"IdRendicionHasta",
			"IdInstrumentoDesde",
			"IdInstrumentoHasta",
		])
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

	def test_hooks_registra_tick_horario(self) -> None:
		from club_management.hooks import scheduler_events

		hourly = scheduler_events.get("hourly") or []
		self.assertIn(
			"club_management.integrations.supervielle.renditions.process_renditions_scheduler_tick",
			hourly,
		)

	def test_tick_inactivo_no_consulta_api(self) -> None:
		session = MagicMock()
		with patch(
			"club_management.integrations.supervielle.renditions.frappe.db.get_single_value",
			return_value=0,
		):
			outcome = process_renditions_scheduler_tick(session=session)
		session.post.assert_not_called()
		self.assertTrue(outcome["skipped"])

	def test_tick_timeout_registra_severidad_high_sin_abortar(self) -> None:
		_CapturingDoc.payloads = []
		session = MagicMock()
		session.post.side_effect = requests.Timeout("read timed out")
		with (
			patch(
				"club_management.integrations.supervielle.renditions.frappe.db.get_single_value",
				return_value=1,
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.db.get_value",
				return_value=None,
			),
			patch(
				"club_management.integrations.supervielle.client.get_runtime_settings",
				return_value=_sandbox_settings(),
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.get_doc",
				side_effect=_CapturingDoc,
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.as_json",
				side_effect=lambda value: str(value),
			),
		):
			outcome = process_renditions_scheduler_tick(session=session)
		self.assertFalse(outcome["skipped"])
		self.assertTrue(outcome.get("error"))
		self.assertTrue(_CapturingDoc.payloads)
		event = _CapturingDoc.payloads[0]
		self.assertEqual(event["doctype"], "Payment Gateway Event")
		self.assertEqual(event["severity"], "High")
		self.assertNotIn("secret", str(event).lower())
		self.assertNotIn("Hash", event.get("event_payload_json") or "")

	def test_tick_http_no_200_registra_severidad_high_sin_abortar(self) -> None:
		_CapturingDoc.payloads = []
		session = MagicMock()
		response = MagicMock()
		response.status_code = 503
		response.json.return_value = {}
		session.post.return_value = response
		with (
			patch(
				"club_management.integrations.supervielle.renditions.frappe.db.get_single_value",
				return_value=1,
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.db.get_value",
				return_value=None,
			),
			patch(
				"club_management.integrations.supervielle.client.get_runtime_settings",
				return_value=_sandbox_settings(),
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.get_doc",
				side_effect=_CapturingDoc,
			),
			patch(
				"club_management.integrations.supervielle.renditions.frappe.as_json",
				side_effect=lambda value: str(value),
			),
		):
			outcome = process_renditions_scheduler_tick(session=session)
		self.assertFalse(outcome["skipped"])
		self.assertIn("503", outcome.get("error") or "")
		self.assertEqual(_CapturingDoc.payloads[0]["severity"], "High")

	def test_tick_http_200_devuelve_preview(self) -> None:
		session = MagicMock()
		session.post.return_value = _ok_response()
		with (
			patch(
				"club_management.integrations.supervielle.renditions.frappe.db.get_single_value",
				return_value=1,
			),
			patch(
				"club_management.integrations.supervielle.client.get_runtime_settings",
				return_value=_sandbox_settings(),
			),
		):
			outcome = process_renditions_scheduler_tick(session=session)
		self.assertFalse(outcome["skipped"])
		self.assertEqual(len(outcome.get("rows") or []), 1)
		self.assertTrue(outcome["rows"][0]["candidate_for_reconciliation"])
