"""Asegura ítem default de bonificación arancel en Club Settings."""

from __future__ import annotations

import frappe

from club_management.finance.setup.icdpe_income_item_groups import LEAF_CARGOS


def execute() -> None:
	code = "BONIFICACION-ARANCEL"
	if not frappe.db.exists("Item", code):
		item_group = (
			frappe.db.get_value("Item Group", {"name": LEAF_CARGOS}, "name")
			or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
			or "Products"
		)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": "Bonificación arancel",
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 0,
			}
		).insert(ignore_permissions=True)
	settings = frappe.get_single("Club Settings")
	if not (settings.item_bonificacion_arancel or "").strip():
		settings.item_bonificacion_arancel = code
		settings.save(ignore_permissions=True)
