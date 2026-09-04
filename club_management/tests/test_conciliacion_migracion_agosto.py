"""Tests conciliación migración agosto (helpers puros).

Spec: `club_management/specs/conciliacion_migracion_agosto.md`
"""

from __future__ import annotations

from unittest import TestCase

from club_management.scripts.alinear_pe_monto_distinto import (
	concepto_exento_mora,
	es_outlier_manual,
	outlier_pendiente,
	resolucion_outlier,
)
from club_management.scripts.conciliacion_migracion_agosto import (
	BUCKETS_OK,
	agregar_por_concepto,
	agregar_por_equipo_grupo,
)


class TestConciliacionMigracionAgosto(TestCase):
	def test_agregar_por_concepto_calcula_gap(self) -> None:
		filas = [
			{
				"concepto_norm": "U17 FLEX",
				"clase": "arancel",
				"monto_csv": 100.0,
				"paid_amount": 100.0,
				"gap": 0.0,
				"bucket": "ok",
			},
			{
				"concepto_norm": "U17 FLEX",
				"clase": "arancel",
				"monto_csv": 50.0,
				"paid_amount": 0.0,
				"gap": 50.0,
				"bucket": "sin_pe_inf",
			},
			{
				"concepto_norm": "CUOTA SOCIAL MENOR",
				"clase": "cuota_social",
				"monto_csv": 30.0,
				"paid_amount": 0.0,
				"gap": 30.0,
				"bucket": "concepto_sin_mapeo",
			},
			{
				"concepto_norm": "SUPERIOR B",
				"clase": "arancel",
				"monto_csv": 28750.0,
				"paid_amount": 25000.0,
				"gap": 3750.0,
				"bucket": "pe_monto_distinto",
			},
		]
		detalle = agregar_por_concepto(filas)
		by = {r["concepto"]: r for r in detalle}
		self.assertEqual(by["U17 FLEX"]["filas_csv"], 2)
		self.assertEqual(by["U17 FLEX"]["monto_csv"], 150.0)
		self.assertEqual(by["U17 FLEX"]["monto_pe"], 100.0)
		self.assertEqual(by["U17 FLEX"]["gap_csv_menos_pe"], 50.0)
		self.assertEqual(by["U17 FLEX"]["filas_faltante"], 1)
		self.assertEqual(by["CUOTA SOCIAL MENOR"]["filas_error"], 1)
		self.assertEqual(by["SUPERIOR B"]["filas_ok"], 1)
		self.assertEqual(by["SUPERIOR B"]["monto_pe"], 25000.0)
		self.assertIn("pe_monto_distinto", BUCKETS_OK)
		self.assertIn("ok_con_mora", BUCKETS_OK)

	def test_c_fed_y_cto_comp_exentos_de_mora(self) -> None:
		self.assertTrue(concepto_exento_mora("C FED U13 FLEX"))
		self.assertTrue(concepto_exento_mora("CTO COMP VOLEY ESC"))
		self.assertTrue(concepto_exento_mora("CTO COMP BASQ TIRA A/B/FLEX"))
		self.assertFalse(concepto_exento_mora("Cuota Social Menor"))
		self.assertFalse(concepto_exento_mora("U15 FLEX"))

	def test_outliers_manuales(self) -> None:
		self.assertTrue(es_outlier_manual("12275", "08/2026", "BOXEO"))
		self.assertTrue(es_outlier_manual("8770", "08/2026", "PATIN INTERMEDIO"))
		self.assertTrue(es_outlier_manual("12235", "08/2026", "CTO COMP VOLEY ESC"))
		self.assertFalse(es_outlier_manual("11389", "08/2026", "AVANZADO 3"))
		self.assertEqual(resolucion_outlier("12275", "08/2026", "BOXEO"), "resuelto_manual")
		self.assertEqual(
			resolucion_outlier("8770", "08/2026", "PATIN INTERMEDIO"),
			"ignorado_error_cobrador",
		)
		self.assertEqual(
			resolucion_outlier("12235", "08/2026", "CTO COMP VOLEY ESC"),
			"liquidado_a_4000",
		)
		self.assertFalse(outlier_pendiente("12275", "08/2026", "BOXEO"))
		self.assertFalse(outlier_pendiente("8770", "08/2026", "PATIN INTERMEDIO"))
		self.assertFalse(outlier_pendiente("12235", "08/2026", "CTO COMP VOLEY ESC"))

	def test_agregar_por_equipo_solo_alias(self) -> None:
		filas = [
			{
				"equipo_alias": "SUPERIOR B",
				"item_codes": "BASQUET / SUPERIOR / AMARILLO",
				"monto_csv": 25000.0,
				"paid_amount": 25000.0,
				"gap": 0.0,
				"bucket": "ok",
			},
			{
				"equipo_alias": "",
				"monto_csv": 1000.0,
				"paid_amount": 0.0,
				"gap": 1000.0,
				"bucket": "sin_pe_inf",
			},
		]
		detalle = agregar_por_equipo_grupo(filas)
		self.assertEqual(len(detalle), 1)
		self.assertEqual(detalle[0]["equipo_grupo"], "SUPERIOR B")
