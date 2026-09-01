"""Tests pipeline cobranza informe prod.

Spec: `club_management/specs/carga_masiva_cobranzas.md`
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.scripts.cobranza_informe_prod_pipeline import run as run_pipeline


class TestCobranzaInformeProdPipeline(FrappeTestCase):
	def test_dry_run_invoca_pasos_y_no_apply(self) -> None:
		with tempfile.TemporaryDirectory() as tmp:
			csv = Path(tmp) / "informe.xlsx"
			csv.write_bytes(b"")
			with patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_fix_tarifas",
				return_value={"parcheadas": 0},
			) as mock_tarifas, patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_sync_ple",
				return_value={"fixed_count": 0},
			), patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_fix_refactura",
				return_value={"parcheadas": 0},
			), patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_alta_cargo",
				return_value={"creados": 0},
			), patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_facturar_cto",
				return_value={"facturados": 0},
			), patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_facturar_cuota_comp",
				return_value={"facturados": 0},
			), patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_bulk_payments",
				return_value={"procesadas": 0, "inconsistencias": []},
			) as mock_apply, patch(
				"club_management.scripts.cobranza_informe_prod_pipeline.run_facturar_sin_factura",
				return_value={"facturados_periodo": 0},
			):
				result = run_pipeline(
					csv_path=str(csv),
					dry_run=True,
					log_dir=str(Path(tmp) / "logs"),
				)
			mock_tarifas.assert_called_once()
			self.assertEqual(mock_apply.call_count, 2)
			self.assertTrue(result["apply"].get("skipped"))

	def test_apply_prod_exige_confirm_en_site_prod(self) -> None:
		original = frappe.local.site
		try:
			frappe.local.site = "gestion.icdpedroechague.com.ar"
			with tempfile.TemporaryDirectory() as tmp:
				csv = Path(tmp) / "informe.xlsx"
				csv.write_bytes(b"")
				with self.assertRaises(frappe.ValidationError):
					run_pipeline(
						csv_path=str(csv),
						dry_run=False,
						log_dir=str(Path(tmp) / "logs"),
						confirm="",
					)
		finally:
			frappe.local.site = original
