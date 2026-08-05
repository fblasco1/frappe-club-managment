"""Tests catálogo de ingresos — jerarquía pilares + hojas."""

from __future__ import annotations

import frappe

from club_management.finance.setup.icdpe_income_item_groups import (
	DEFAULT_ITEM_GROUP_ROOT,
	INGRESO_LEAF_GROUPS,
	INGRESO_PILLARS,
	INGRESO_SOCIOS,
	LEAF_BASQUET,
	LEAF_CARGOS,
	LEAF_CUOTAS,
	LEAF_DONACIONES,
	MID_DEPORTES,
	ensure_ingresos_item_group_tree,
	resolve_ingreso_leaf_for_item,
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

	def test_resolve_leaf_basquet_y_cuota(self) -> None:
		self.assertEqual(resolve_ingreso_leaf_for_item("ICDPE-CUOTA-SOCIAL"), LEAF_CUOTAS)
		self.assertEqual(resolve_ingreso_leaf_for_item("RECARGO-MORA"), LEAF_CARGOS)
		self.assertEqual(resolve_ingreso_leaf_for_item("ICDPE-BASQUET-ESCUELITA"), LEAF_BASQUET)
		self.assertEqual(resolve_ingreso_leaf_for_item("ICDPE-FIN-DONACION"), LEAF_DONACIONES)

	def test_ensure_tree_pilares_nodos_y_hojas(self) -> None:
		run_ingresos_item_groups_migration()
		for pillar in INGRESO_PILLARS:
			self.assertTrue(frappe.db.exists("Item Group", pillar), msg=pillar)
			self.assertEqual(
				frappe.db.get_value("Item Group", pillar, "parent_item_group"),
				DEFAULT_ITEM_GROUP_ROOT,
			)
			self.assertEqual(int(frappe.db.get_value("Item Group", pillar, "is_group") or 0), 1)
			self.assertEqual(frappe.db.count("Item", {"item_group": pillar}), 0, msg=pillar)

		self.assertTrue(frappe.db.exists("Item Group", LEAF_CUOTAS))
		self.assertEqual(
			frappe.db.get_value("Item Group", LEAF_CUOTAS, "parent_item_group"),
			INGRESO_SOCIOS,
		)
		self.assertEqual(int(frappe.db.get_value("Item Group", LEAF_CUOTAS, "is_group") or 0), 0)

		self.assertTrue(frappe.db.exists("Item Group", MID_DEPORTES))
		self.assertEqual(int(frappe.db.get_value("Item Group", MID_DEPORTES, "is_group") or 0), 1)
		self.assertEqual(
			frappe.db.get_value("Item Group", LEAF_BASQUET, "parent_item_group"),
			MID_DEPORTES,
		)

	def test_migracion_mueve_item_a_hoja(self) -> None:
		ensure_ingresos_item_group_tree()
		# ítem en pilar plano (simula fase previa)
		if not frappe.db.exists("Item Group", INGRESO_SOCIOS):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": INGRESO_SOCIOS,
					"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)

		code = "TEST-ING-JERARQUIA-CUOTA"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Test jerarquía cuota",
				"item_group": INGRESO_SOCIOS,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True)
		# Forzar mapeo vía prefijo/fallback: registrar como cuota-like usando resolve
		# El código de test cae en LEAF_CARGOS por fallback; lo movemos explícito:
		from club_management.finance.setup import icdpe_income_item_groups as mod

		mod.ITEM_TO_LEAF[code] = LEAF_CUOTAS
		try:
			run_ingresos_item_groups_migration()
			self.assertEqual(frappe.db.get_value("Item", code, "item_group"), LEAF_CUOTAS)
			self.assertEqual(frappe.db.count("Item", {"item_group": INGRESO_SOCIOS}), 0)

			run_ingresos_item_groups_migration()
			self.assertEqual(frappe.db.get_value("Item", code, "item_group"), LEAF_CUOTAS)
		finally:
			mod.ITEM_TO_LEAF.pop(code, None)

	def test_leaf_groups_list(self) -> None:
		self.assertIn(LEAF_CUOTAS, INGRESO_LEAF_GROUPS)
		self.assertIn(LEAF_BASQUET, INGRESO_LEAF_GROUPS)
		self.assertNotIn(INGRESO_SOCIOS, INGRESO_LEAF_GROUPS)
		self.assertNotIn(MID_DEPORTES, INGRESO_LEAF_GROUPS)
