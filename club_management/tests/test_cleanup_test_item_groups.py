"""Tests limpieza `_Test Item Group*` (spec cleanup_test_item_groups.md)."""

from __future__ import annotations

import frappe

from club_management.finance.setup.cleanup_test_item_groups import (
	TEST_ITEM_GROUP_PREFIX,
	run_cleanup_test_item_groups,
)
from club_management.finance.setup.icdpe_finance_items import DEFAULT_ITEM_GROUP_ROOT
from club_management.members.test_helpers import MembersTestCase


class TestCleanupTestItemGroups(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("All Item Groups ausente")

	def test_elimina_grupo_e_item_test(self) -> None:
		gname = f"{TEST_ITEM_GROUP_PREFIX} Cleanup Unit"
		if frappe.db.exists("Item Group", gname):
			# vaciar primero
			for code in frappe.get_all("Item", filters={"item_group": gname}, pluck="name"):
				frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
			frappe.delete_doc("Item Group", gname, force=1, ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": gname,
				"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		code = "_Test Cleanup Item XYZ"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": gname,
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True)

		run_cleanup_test_item_groups()

		self.assertFalse(frappe.db.exists("Item", code))
		self.assertFalse(frappe.db.exists("Item Group", gname))
