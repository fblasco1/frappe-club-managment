"""Tests estáticos UI cancelar factura impaga (spec cancelar_factura_venta_impaga.md)."""

from __future__ import annotations

import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestCancelarFacturaVentaImpagaUi(unittest.TestCase):
	def test_socio_js_tiene_boton_y_api(self) -> None:
		js = (PACKAGE_ROOT / "doctype" / "socio" / "socio.js").read_text(encoding="utf-8")
		self.assertIn("Cancelar factura impaga", js)
		self.assertIn("dialog_cancelar_factura_impaga", js)
		self.assertIn("list_facturas_impagas_cancelables", js)
		self.assertIn("cancelar_factura_venta", js)

	def test_api_whitelist_expuesta(self) -> None:
		api = (PACKAGE_ROOT / "api" / "cobranza_desk.py").read_text(encoding="utf-8")
		self.assertIn("def cancelar_factura_venta", api)
		self.assertIn("def list_facturas_impagas_cancelables", api)


if __name__ == "__main__":
	unittest.main()
