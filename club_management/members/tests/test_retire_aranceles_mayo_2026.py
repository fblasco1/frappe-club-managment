"""Tests retiro seed aranceles Mayo 2026."""

from __future__ import annotations

import frappe

from club_management.activities.services.retire_aranceles_mayo_2026 import (
	MAYO_ITEM_PREFIX,
	retire_aranceles_mayo_2026,
)
from club_management.members.test_helpers import MembersTestCase


class TestRetireArancelesMayo2026(MembersTestCase):
	def test_retire_elimina_items_mayo26(self) -> None:
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		code = f"{MAYO_ITEM_PREFIX}-test-retire"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"stock_uom": "Nos",
				}
			).insert(ignore_permissions=True)

		retire_aranceles_mayo_2026()
		self.assertFalse(frappe.db.exists("Item", code))
