"""Tests UI strings: cobro multi-factura / medios mixtos en socio.js."""

from __future__ import annotations

import unittest
from pathlib import Path

_SOCIO_JS = Path(__file__).resolve().parents[1] / "doctype" / "socio" / "socio.js"


class TestCobroMultiFacturaUi(unittest.TestCase):
	def test_socio_js_tiene_multiselect_y_medios_mixtos(self) -> None:
		text = _SOCIO_JS.read_text(encoding="utf-8")
		self.assertIn("prompt_cobro_multi_factura", text)
		self.assertIn("MultiCheck", text)
		self.assertIn("registrar_cobro_compuesto", text)
		self.assertIn("medios", text)
		self.assertIn("Segundo medio", text)
		self.assertIn("mora_resumen", text)
		self.assertIn("preview_mora_al_cobro", text)
		self.assertIn("_pintar_resumen_mora", text)
		self.assertIn("_aplicar_preview_mora", text)
		self.assertIn("_actualizar_labels_facturas_mora", text)
		# MultiCheck dispara on_change (no onchange).
		self.assertIn("sales_invoices.df.on_change", text)
		self.assertIn("_fmt_money", text)
		self.assertNotIn("frappe.format(monto, { fieldtype: \"Currency\" })", text)
