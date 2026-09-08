"""Tests de parsers de Excel de administración (informe cobranzas / socios)."""

from __future__ import annotations

from datetime import datetime

from club_management.members.test_helpers import MembersTestCase
from club_management.scripts.excel_inscripciones import map_seleccion_excel
from club_management.scripts.informe_cobranzas import map_medio_nota, pagos_from_informe_rows, parse_periodo_informe


class TestInformeCobranzasParse(MembersTestCase):
	def test_periodo_agosto_26(self) -> None:
		self.assertEqual(parse_periodo_informe("AGOSTO 26"), "08/2026")
		self.assertEqual(parse_periodo_informe("JULIO 2026"), "07/2026")
		self.assertEqual(parse_periodo_informe("SEPTIEMRBE"), "09/2026")
		self.assertEqual(
			parse_periodo_informe("JULIO", fecha=datetime(2026, 8, 10).date()),
			"07/2026",
		)

	def test_medio_trans(self) -> None:
		self.assertEqual(map_medio_nota("trans"), "Transferencia")
		self.assertEqual(map_medio_nota("tras"), "Transferencia")
		self.assertEqual(map_medio_nota(None), "Efectivo")

	def test_pagos_agrupados_por_concepto(self) -> None:
		rows = [
			("INFORME DE COBRANZAS", None, None, None, None, None, None, None, None),
			("Concepto:  U17 FLEX", None, None, None, None, None, None, None, None),
			("Fecha", "Socio", None, "Período", "Importe", "Cobrador", "Comisión", None, "Notas"),
			(datetime(2026, 8, 10), 11984, "BENITEZ", "JULIO 2026", 30475, 0, 0, 0, "trans"),
			("Subtotales:", None, None, None, 30475, None, None, 0, None),
		]
		pagos = pagos_from_informe_rows(rows)
		self.assertEqual(len(pagos), 1)
		self.assertEqual(pagos[0]["nro_socio"], "11984")
		self.assertEqual(pagos[0]["periodo"], "07/2026")
		self.assertEqual(pagos[0]["medio_pago"], "Transferencia")
		self.assertEqual(pagos[0]["concepto"], "U17 FLEX")


class TestExcelInscripcionesMap(MembersTestCase):
	def test_omite_adherente(self) -> None:
		sels, code = map_seleccion_excel("ADHERENTE", "", "")
		self.assertEqual(sels, [])
		self.assertEqual(code, "omitido_sin_deporte")

	def test_basquet_escuela_u9(self) -> None:
		sels, code = map_seleccion_excel("BASQUET", "ESCUELA", "U9")
		self.assertIsNone(code)
		self.assertEqual(sels[0]["actividad"], "Basquet")
		self.assertEqual(sels[0]["grupo"], "Mixto / Escuela")
		self.assertEqual(sels[0]["equipo"], "U7 / U9")

	def test_voley_escuela(self) -> None:
		sels, _code = map_seleccion_excel("VOLEY", "ESCUELA", "")
		self.assertEqual(sels[0]["actividad"], "Voley Femenino")
		self.assertEqual(sels[0]["grupo"], "Escuelita Minivoley")
