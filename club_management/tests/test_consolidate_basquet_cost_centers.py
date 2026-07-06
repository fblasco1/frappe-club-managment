"""Tests consolidación CC básquet ICDPE (spec basquet_cost_center_consolidado.md)."""

from __future__ import annotations

import frappe

from club_management.activities.data.basquet_aranceles_icdpe import BASQUET_ITEM_SPECS
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.basquet_cost_center import (
	BASQUET_COST_CENTER,
	BASQUET_COST_CENTER_PARENT,
	LEGACY_BASQUET_COST_CENTERS,
)
from club_management.setup.consolidate_basquet_cost_centers import (
	consolidate_basquet_cost_centers,
	ensure_basquet_unified_cost_center,
)
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestConsolidateBasquetCostCenters(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada en el sitio")
		if not frappe.db.exists("Cost Center", BASQUET_COST_CENTER_PARENT):
			self.skipTest("Falta CC padre Deportes - ICDPE")

	def _ensure_legacy_cc(self, full_name: str) -> str:
		if frappe.db.exists("Cost Center", full_name):
			frappe.db.set_value("Cost Center", full_name, "disabled", 0, update_modified=False)
			return full_name
		short = full_name.replace(" - ICDPE", "")
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": short,
				"parent_cost_center": BASQUET_COST_CENTER_PARENT,
				"company": resolve_icdpe_company(),
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		return full_name

	def _ensure_item_with_cc(self, item_code: str, cost_center: str) -> None:
		company = resolve_icdpe_company()
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": "All Item Groups",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		item = frappe.get_doc("Item", item_code)
		row = next((d for d in item.item_defaults or [] if d.company == company), None)
		if row is None:
			item.append(
				"item_defaults",
				{
					"company": company,
					"selling_cost_center": cost_center,
				},
			)
		else:
			row.selling_cost_center = cost_center
		item.save(ignore_permissions=True)

	def test_basquet_item_specs_usan_cc_unificado(self) -> None:
		cost_centers = {spec.cost_center for spec in BASQUET_ITEM_SPECS}
		self.assertEqual(cost_centers, {BASQUET_COST_CENTER})

	def test_ensure_basquet_unified_cost_center(self) -> None:
		if frappe.db.exists("Cost Center", BASQUET_COST_CENTER):
			frappe.delete_doc("Cost Center", BASQUET_COST_CENTER, force=1)

		name = ensure_basquet_unified_cost_center()
		self.assertEqual(name, BASQUET_COST_CENTER)
		self.assertTrue(frappe.db.exists("Cost Center", BASQUET_COST_CENTER))

	def test_consolidate_reasigna_item_defaults(self) -> None:
		legacy = self._ensure_legacy_cc(LEGACY_BASQUET_COST_CENTERS[0])
		item_code = "TEST-BASQUET-CC-CONSOLIDATE"
		self._ensure_item_with_cc(item_code, legacy)

		result = consolidate_basquet_cost_centers(disable_legacy=True)
		self.assertIn(item_code, result["items_updated"])

		company = resolve_icdpe_company()
		item = frappe.get_doc("Item", item_code)
		row = next(d for d in item.item_defaults if d.company == company)
		self.assertEqual(row.selling_cost_center, BASQUET_COST_CENTER)
		self.assertEqual(frappe.db.get_value("Cost Center", legacy, "disabled"), 1)
