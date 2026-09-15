"""Tests: centro de costo dedicado para la Cuota Social.

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.

La cuota social debe imputar a un centro de costo propio («Cuotas Sociales»),
tanto en la línea de la factura como en el asiento contable.
"""

from __future__ import annotations

import frappe

from club_management.finance.setup.cuota_social_cost_center import (
	ensure_cuota_social_cost_center,
)
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	_default_company,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCuotaSocialCostCenter(MembersTestCase):
	_REFERENCE = "2026-07-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		if not settings.company:
			settings.company = frappe.db.get_value("Company", {}, "name")
		settings.save(ignore_permissions=True)
		self._company = _default_company()
		if not self._company:
			self.skipTest("No hay Company configurada en el sitio")
		self._ensure_cuota_item()
		self._cc = ensure_cuota_social_cost_center(self._company)

	def _ensure_cuota_item(self) -> None:
		if frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": CUOTA_SOCIAL_ITEM_CODE,
				"item_name": "Cuota Social Base",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 29_000,
			}
		).insert(ignore_permissions=True)

	def test_setup_crea_cost_center_y_item_default(self) -> None:
		self.assertTrue(frappe.db.exists("Cost Center", self._cc))
		abbr = frappe.get_cached_value("Company", self._company, "abbr")
		self.assertEqual(self._cc, f"Cuotas Sociales - {abbr}")
		item = frappe.get_doc("Item", CUOTA_SOCIAL_ITEM_CODE)
		row = next(d for d in item.item_defaults if d.company == self._company)
		self.assertEqual(row.selling_cost_center, self._cc)

	def test_factura_cuota_imputa_a_cuotas_sociales(self) -> None:
		socio = insert_socio(dni="74008001", email="cuota.cc@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test CC cuota social")
		invoice = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(invoice)

		doc = frappe.get_doc("Sales Invoice", invoice)
		fila = next(r for r in doc.items if r.item_code == CUOTA_SOCIAL_ITEM_CODE)
		self.assertEqual(fila.cost_center, self._cc)

		gl = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": invoice, "credit": [">", 0], "is_cancelled": 0},
			fields=["cost_center"],
		)
		self.assertTrue(gl)
		for row in gl:
			self.assertEqual(row["cost_center"], self._cc)
