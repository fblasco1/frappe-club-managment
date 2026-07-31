"""Tests catálogo de ingresos — 4 pilares Item Group."""

from __future__ import annotations

import frappe

from club_management.finance.setup.icdpe_income_item_groups import (
	DEFAULT_ITEM_GROUP_ROOT,
	INGRESO_ACTIVIDADES,
	INGRESO_COMERCIALES,
	INGRESO_INSTITUCIONALES,
	INGRESO_PILLARS,
	INGRESO_SOCIOS,
	LEGACY_INCOME_GROUP_TO_PILLAR,
	ensure_ingresos_item_group_tree,
	run_ingresos_item_groups_migration,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestCatalogoIngresosItemGroups(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("Item Group raíz ausente")

	def test_ensure_cuatro_pilares(self) -> None:
		ensure_ingresos_item_group_tree()
		for pillar in INGRESO_PILLARS:
			self.assertTrue(frappe.db.exists("Item Group", pillar), msg=pillar)
			self.assertEqual(
				frappe.db.get_value("Item Group", pillar, "parent_item_group"),
				DEFAULT_ITEM_GROUP_ROOT,
			)
			self.assertEqual(int(frappe.db.get_value("Item Group", pillar, "is_group") or 0), 0)

	def test_migracion_reasigna_por_grupo_y_codigo(self) -> None:
		# Fixture mínimo: grupo viejo + ítem, y un FIN institucional.
		old = next(iter(LEGACY_INCOME_GROUP_TO_PILLAR))
		pillar = LEGACY_INCOME_GROUP_TO_PILLAR[old]
		if not frappe.db.exists("Item Group", old):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": old,
					"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)

		code = "TEST-ING-MIG-CUOTA"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Test migración ingreso",
				"item_group": old,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)

		fin_code = "ICDPE-FIN-DONACION"
		had_fin = frappe.db.exists("Item", fin_code)

		run_ingresos_item_groups_migration()

		self.assertEqual(frappe.db.get_value("Item", code, "item_group"), pillar)
		if had_fin:
			self.assertEqual(
				frappe.db.get_value("Item", fin_code, "item_group"),
				INGRESO_INSTITUCIONALES,
			)

		# Idempotencia
		run_ingresos_item_groups_migration()
		self.assertEqual(frappe.db.get_value("Item", code, "item_group"), pillar)

	def test_pilares_conocidos(self) -> None:
		self.assertIn(INGRESO_SOCIOS, INGRESO_PILLARS)
		self.assertIn(INGRESO_ACTIVIDADES, INGRESO_PILLARS)
		self.assertIn(INGRESO_COMERCIALES, INGRESO_PILLARS)
		self.assertIn(INGRESO_INSTITUCIONALES, INGRESO_PILLARS)
