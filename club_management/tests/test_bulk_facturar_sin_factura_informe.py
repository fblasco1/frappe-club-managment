"""Tests facturación sin factura (no CTO COMP) desde informe/log apply.

Spec: `club_management/specs/informe_concepto_cobranza.md`
"""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.scripts.bulk_facturar_sin_factura_informe import collect_filas_a_facturar


class TestBulkFacturarSinFacturaInforme(MembersTestCase):
	def test_collect_excluye_cto_comp_desde_inconsistencias(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / "apply.inconsistencias.csv"
			with path.open("w", encoding="utf-8", newline="") as fh:
				writer = csv.DictWriter(
					fh,
					fieldnames=["codigo", "socio", "periodo", "concepto", "monto_abonado", "fila"],
				)
				writer.writeheader()
				writer.writerow(
					{
						"codigo": "sin_factura_impaga",
						"socio": "1001",
						"periodo": "06/2026",
						"concepto": "Cuota Social Menor",
						"monto_abonado": "29500",
						"fila": "10",
					}
				)
				writer.writerow(
					{
						"codigo": "sin_factura_impaga",
						"socio": "1002",
						"periodo": "08/2026",
						"concepto": "CTO COMP VOLEY ESC",
						"monto_abonado": "6000",
						"fila": "11",
					}
				)
				writer.writerow(
					{
						"codigo": "monto_discordante",
						"socio": "1003",
						"periodo": "08/2026",
						"concepto": "Cuota Social Activo",
						"monto_abonado": "35000",
						"fila": "12",
					}
				)

			rows = collect_filas_a_facturar(str(path), source="inconsistencias")
			self.assertEqual(len(rows), 1)
			self.assertEqual(rows[0]["concepto"], "Cuota Social Menor")

	def test_collect_desde_apply_json(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			path = Path(tmp) / "apply_cobranzas_v8.json"
			path.write_text(
				json.dumps(
					{
						"inconsistencias": [
							{
								"codigo": "sin_factura_impaga",
								"socio": "2001",
								"periodo": "05/2026",
								"concepto": "PRE-MINI A U9",
								"monto_abonado": 12000,
							}
						]
					}
				),
				encoding="utf-8",
			)
			rows = collect_filas_a_facturar(str(path), source="apply_json")
			self.assertEqual(len(rows), 1)
			self.assertEqual(rows[0]["socio"], "2001")
