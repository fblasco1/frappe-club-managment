"""Tests catálogo jerárquico de egresos (Item Groups + Items)."""

from __future__ import annotations

import frappe

from club_management.finance.setup.icdpe_finance_items import (
	DEFAULT_ITEM_GROUP_ROOT,
	EGRESO_CENTRAL_GROUPS,
	EGRESO_LEAF_GROUPS,
	EGRESO_TREE,
	EXPENSE_SPECS,
	LEGACY_EXPENSE_ITEMS_TO_DISABLE,
	ensure_egresos_item_group_tree,
	run_finance_items_seed,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestCatalogoEgresosItemGroups(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		try:
			self.company = resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("Item Group raíz ausente")

	def test_ensure_tree_cuatro_pilares(self) -> None:
		ensure_egresos_item_group_tree()
		for central in EGRESO_CENTRAL_GROUPS:
			self.assertTrue(frappe.db.exists("Item Group", central), msg=central)
			self.assertEqual(
				frappe.db.get_value("Item Group", central, "parent_item_group"),
				DEFAULT_ITEM_GROUP_ROOT,
				msg=central,
			)
			self.assertEqual(int(frappe.db.get_value("Item Group", central, "is_group") or 0), 1)

		for central, leaves in EGRESO_TREE.items():
			for leaf in leaves:
				self.assertTrue(frappe.db.exists("Item Group", leaf), msg=leaf)
				self.assertEqual(
					frappe.db.get_value("Item Group", leaf, "parent_item_group"),
					central,
					msg=leaf,
				)
				self.assertEqual(int(frappe.db.get_value("Item Group", leaf, "is_group") or 0), 0)

	def test_seed_items_no_stock_en_grupo(self) -> None:
		result = run_finance_items_seed()
		self.assertIn("created", result)
		created_or_updated = 0
		for spec in EXPENSE_SPECS:
			if not frappe.db.exists("Item", spec.item_code):
				continue
			created_or_updated += 1
			item = frappe.get_doc("Item", spec.item_code)
			self.assertEqual(int(item.is_stock_item or 0), 0, msg=spec.item_code)
			self.assertEqual(int(item.is_purchase_item or 0), 1, msg=spec.item_code)
			self.assertEqual(item.item_group, spec.item_group, msg=spec.item_code)
			self.assertEqual(int(item.disabled or 0), 0, msg=spec.item_code)
		if created_or_updated == 0 and result.get("skipped", 0) == len(EXPENSE_SPECS):
			self.skipTest("Cuentas/CC de egreso ausentes en el sitio")
		self.assertGreater(created_or_updated, 0)

	def test_legacy_deshabilitados(self) -> None:
		run_finance_items_seed()
		for code in LEGACY_EXPENSE_ITEMS_TO_DISABLE:
			if not frappe.db.exists("Item", code):
				continue
			self.assertEqual(
				int(frappe.db.get_value("Item", code, "disabled") or 0),
				1,
				msg=code,
			)

	def test_seed_idempotente(self) -> None:
		run_finance_items_seed()
		again = run_finance_items_seed()
		self.assertEqual(again.get("error", 0), 0)
		ensure_egresos_item_group_tree()
		self.assertTrue(frappe.db.exists("Item Group", EGRESO_LEAF_GROUPS[0]))
