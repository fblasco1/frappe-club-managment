"""Tests informe HTML cobranza socio a socio."""

from __future__ import annotations

from club_management.members.services.cobranza_import_report import (
	_suggest_cobranza_action,
	build_cobranza_followup_rows,
	index_cobranza_log_by_socio,
	render_cobranza_import_sections_html,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCobranzaImportReport(MembersTestCase):
	def test_index_cobranza_log_by_socio(self) -> None:
		log = {
			"ok": [{"socio": "1001", "payment_entry": "PE-1"}],
			"omitidos_detalle": [{"socio": "1002", "motivo": "Sin factura"}],
			"errores_detalle": [{"socio": "1003", "error": "Socio no encontrado"}],
		}
		indexed = index_cobranza_log_by_socio(log)
		self.assertEqual(len(indexed["1001"]["ok"]), 1)
		self.assertEqual(indexed["1002"]["omitidos"][0]["motivo"], "Sin factura")
		self.assertEqual(indexed["1003"]["errores"][0]["error"], "Socio no encontrado")

	def test_suggest_action_sin_factura_aranceles(self) -> None:
		accion = _suggest_cobranza_action(
			facturas=[],
			cobranza_rows={},
			tiene_inscripcion_nueva=True,
		)
		self.assertIn("Emitir aranceles", accion)

	def test_render_incluye_secciones_excel(self) -> None:
		log = {
			"resumen": {"procesados": 1, "omitidos": 1, "errores": 1},
			"ok": [{"fecha": "2026-07-01", "socio": "1", "concepto": "CUOTA", "importe": 100}],
			"omitidos_detalle": [
				{"fecha": "2026-07-02", "socio": "2", "motivo": "Sin factura", "concepto": "U15"}
			],
			"errores_detalle": [{"fecha": "2026-07-03", "socio": "3", "error": "Socio no encontrado"}],
			"file_path": "/tmp/test.xlsx",
			"fecha_desde": "2026-07-01",
			"fecha_hasta": "2026-07-07",
		}
		html = render_cobranza_import_sections_html(log, periodo_cobro="07/2026")
		self.assertIn("Cobranza — qué corregir a mano", html)
		self.assertIn("Excel cobranza — omitidos", html)
		self.assertIn("Sin factura", html)

	def test_build_followup_row_para_inscripcion_nueva(self) -> None:
		socio = insert_socio(dni="88110001", email="cob.report@example.com", estado="Activo")
		rows = build_cobranza_followup_rows(
			[
				{
					"socio": socio.name,
					"dni": socio.dni,
					"nombre": "TEST, Cobranza",
					"destino": "Basquet (Azul — U13)",
				}
			],
			periodo_cobro="07/2026",
			cobranza_log=None,
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["socio"], socio.name)
		self.assertIn("Emitir aranceles", rows[0]["accion"])
