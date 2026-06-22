"""Crea ítems de arancel mensual deportivo ICDPE con tarifas."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.activities.data.arancel_item_spec import ArancelItemSpec
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_create_service_items import (
	_ensure_item_group,
	_ensure_uom,
	_resolve_cost_center,
	_resolve_income_account,
	_upsert_item_default,
)


def upsert_arancel_item(spec: ArancelItemSpec) -> str:
	company = resolve_icdpe_company()
	_ensure_item_group("ICDPE / Aranceles deportes")
	_resolve_cost_center(company, spec.cost_center)
	income_account = _resolve_income_account(company, "412001")

	if frappe.db.exists("Item", spec.item_code):
		item = frappe.get_doc("Item", spec.item_code)
		changed = False
		if item.item_name != spec.item_name:
			item.item_name = spec.item_name
			changed = True
		if item.item_group != "ICDPE / Aranceles deportes":
			item.item_group = "ICDPE / Aranceles deportes"
			changed = True
		if int(item.disabled or 0):
			item.disabled = 0
			changed = True
		if changed:
			item.save(ignore_permissions=True)
		action = "updated"
	else:
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": spec.item_code,
				"item_name": spec.item_name,
				"item_group": "ICDPE / Aranceles deportes",
				"is_stock_item": 0,
				"is_sales_item": 1,
				"stock_uom": "Servicio",
				"include_item_in_manufacturing": 0,
			}
		).insert(ignore_permissions=True)
		action = "created"

	_upsert_item_default(spec.item_code, company, income_account, spec.cost_center)
	frappe.db.set_value("Item", spec.item_code, "standard_rate", flt(spec.rate), update_modified=False)
	return action


def sync_arancel_items(specs: tuple[ArancelItemSpec, ...]) -> list[dict[str, str]]:
	_ensure_uom("Servicio")
	results: list[dict[str, str]] = []
	for spec in specs:
		action = upsert_arancel_item(spec)
		results.append({"item_code": spec.item_code, "action": action, "rate": str(spec.rate)})
	return results
