"""Tests corrección Sponsors y ventas (spec fix_sponsors_y_ventas.md)."""

from __future__ import annotations

import frappe

from club_management.finance.setup.fix_sponsors_y_ventas import (
	SPONSOR_CANONICAL,
	SPONSOR_DUPLICATE,
	run_fix_sponsors_y_ventas,
)
from club_management.finance.setup.icdpe_finance_items import (
	DEFAULT_ITEM_GROUP_ROOT,
	GROUP_SERVICIOS_PUB,
	ensure_egresos_item_group_tree,
)
from club_management.finance.setup.icdpe_income_item_groups import (
	LEAF_CARGOS,
	LEAF_SPONSORS,
	ensure_ingresos_item_group_tree,
	resolve_ingreso_leaf_for_item,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestFixSponsorsYVentas(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("All Item Groups ausente")
		ensure_egresos_item_group_tree()
		ensure_ingresos_item_group_tree()

	def _ensure_item(self, code: str, group: str, *, purchase: int = 0, sales: int = 1) -> None:
		if frappe.db.exists("Item", code):
			frappe.db.set_value("Item", code, "item_group", group)
			frappe.db.set_value("Item", code, "is_purchase_item", purchase)
			frappe.db.set_value("Item", code, "is_sales_item", sales)
			frappe.db.set_value("Item", code, "disabled", 0)
			return
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"is_stock_item": 0,
				"is_purchase_item": purchase,
				"is_sales_item": sales,
			}
		).insert(ignore_permissions=True)

	def test_resolve_fin_egreso_no_va_a_sponsors(self) -> None:
		self.assertNotEqual(resolve_ingreso_leaf_for_item("ICDPE-FIN-LUZ"), LEAF_SPONSORS)
		self.assertEqual(resolve_ingreso_leaf_for_item(SPONSOR_CANONICAL), LEAF_SPONSORS)

	def test_reassign_luz_desde_sponsors(self) -> None:
		self._ensure_item("ICDPE-FIN-LUZ", LEAF_SPONSORS, purchase=1, sales=0)
		run_fix_sponsors_y_ventas()
		self.assertEqual(
			frappe.db.get_value("Item", "ICDPE-FIN-LUZ", "item_group"),
			GROUP_SERVICIOS_PUB,
		)

	def test_sponsor_pub_disabled_canonico_activo(self) -> None:
		self._ensure_item(SPONSOR_CANONICAL, LEAF_SPONSORS, purchase=0, sales=1)
		self._ensure_item(SPONSOR_DUPLICATE, LEAF_SPONSORS, purchase=0, sales=1)
		run_fix_sponsors_y_ventas()
		self.assertEqual(int(frappe.db.get_value("Item", SPONSOR_DUPLICATE, "disabled") or 0), 1)
		self.assertEqual(int(frappe.db.get_value("Item", SPONSOR_CANONICAL, "disabled") or 0), 0)
		self.assertEqual(
			frappe.db.get_value("Item", SPONSOR_CANONICAL, "item_group"),
			LEAF_SPONSORS,
		)
