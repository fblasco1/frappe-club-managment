"""Tests facturación CTO COMP cruzada con informe.

Spec: `club_management/specs/informe_concepto_cobranza.md`
"""

from __future__ import annotations

import frappe

from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.scripts.informe_concepto_cobranza import (
	buscar_cargo_pendiente_cuota_complementaria,
	buscar_cargo_socio_cuota_complementaria,
	cuotas_complementarias_equivalentes,
	necesita_alta_cargo_cto_comp,
	necesita_facturacion_cto_comp,
)


class TestFacturarCtoCompInforme(MembersTestCase):
	_ITEM = "ICDPE-CARGO-VARIOS"

	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("Item", self._ITEM):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self._ITEM,
					"item_name": self._ITEM,
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)

	def _socio(self):
		socio = insert_socio(dni="79001001", email="cto.informe@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test CTO informe")
		return socio

	def _cargo(self, socio_name: str, titulo: str) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": socio_name,
					"titulo": titulo,
					"tipo_cargo": "Otro",
					"modo_cobro": "Recurrente",
					"item": self._ITEM,
					"monto": 6000,
					"fecha_desde": "2026-08-01",
					"fecha_hasta": "2026-12-31",
					"estado": "Pendiente",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_buscar_cargo_pendiente_fuzzy_titulo(self) -> None:
		socio = self._socio()
		self._cargo(socio.name, "CTO COMP BASQUET TIRA A/B/FLEX")
		found = buscar_cargo_pendiente_cuota_complementaria(
			socio.name, "CTO COMP BASQ TIRA A/B/FLEX"
		)
		self.assertIsNotNone(found)
		self.assertTrue(
			cuotas_complementarias_equivalentes(
				"CTO COMP BASQ TIRA A/B/FLEX", found.get("titulo")
			)
		)

	def test_necesita_facturacion_sin_si(self) -> None:
		socio = self._socio()
		self._cargo(socio.name, "CTO COMP VOLEY ESC")
		self.assertTrue(
			necesita_facturacion_cto_comp(socio.name, "08/2026", "CTO COMP VOLEY ESC")
		)

	def test_necesita_facturacion_false_sin_cargo(self) -> None:
		socio = self._socio()
		self.assertFalse(
			necesita_facturacion_cto_comp(socio.name, "08/2026", "CTO COMP VOLEY")
		)

	def test_necesita_alta_sin_cargo_ni_si(self) -> None:
		socio = self._socio()
		self.assertTrue(
			necesita_alta_cargo_cto_comp(socio.name, "08/2026", "CTO COMP BASQ ESC/FEM")
		)

	def test_necesita_alta_false_si_existe_cargo(self) -> None:
		socio = self._socio()
		self._cargo(socio.name, "CTO COMP VOLEY ESC")
		self.assertFalse(
			necesita_alta_cargo_cto_comp(socio.name, "08/2026", "CTO COMP VOLEY ESC")
		)
		self.assertIsNotNone(
			buscar_cargo_socio_cuota_complementaria(socio.name, "CTO COMP VOLEY ESC")
		)
