"""Contrato de consulta y preview de rendiciones Supervielle v6.2."""

from __future__ import annotations

import unittest

from club_management.integrations.supervielle.renditions import (
	build_rendition_request,
	parse_renditions_preview,
)


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
