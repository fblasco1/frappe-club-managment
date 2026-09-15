"""Corrige hoja Sponsors y ventas: egresos a sus hojas + sponsor canónico.

Spec: ``fix_sponsors_y_ventas.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.finance.setup.icdpe_finance_items import (
	EXPENSE_SPECS,
	ensure_egresos_item_group_tree,
)
from club_management.finance.setup.icdpe_income_item_groups import LEAF_SPONSORS

SPONSOR_CANONICAL = "ICDPE-FIN-SPONSOR"
SPONSOR_DUPLICATE = "ICDPE-SPONSOR-PUB"

# Ingresos que deben permanecer en Sponsors y ventas.
SPONSORS_INCOME_CODES: frozenset[str] = frozenset(
	{
		SPONSOR_CANONICAL,
		SPONSOR_DUPLICATE,  # disabled, pero mismo grupo
		"ICDPE-FIN-INDUMENTARIA",
		"ICDPE-VENTA-INDUMENTARIA",
	}
)


def expense_item_codes() -> frozenset[str]:
	return frozenset(spec.item_code for spec in EXPENSE_SPECS)


def reassign_expense_specs_from_sponsors() -> dict[str, int]:
	"""Mueve ítems de EXPENSE_SPECS a su item_group canónico (desde Sponsors u otro)."""
	ensure_egresos_item_group_tree()
	counts: dict[str, int] = {}
	for spec in EXPENSE_SPECS:
		if not frappe.db.exists("Item", spec.item_code):
			continue
		if not frappe.db.exists("Item Group", spec.item_group):
			continue
		cur = frappe.db.get_value("Item", spec.item_code, "item_group")
		if cur == spec.item_group:
			continue
		frappe.db.set_value(
			"Item",
			spec.item_code,
			"item_group",
			spec.item_group,
			update_modified=False,
		)
		counts[spec.item_group] = counts.get(spec.item_group, 0) + 1
	return counts


def disable_duplicate_sponsor_pub() -> bool:
	"""Deja ICDPE-FIN-SPONSOR como canónico; apaga ICDPE-SPONSOR-PUB."""
	if not frappe.db.exists("Item", SPONSOR_DUPLICATE):
		return False
	changed = False
	if int(frappe.db.get_value("Item", SPONSOR_DUPLICATE, "disabled") or 0) != 1:
		frappe.db.set_value("Item", SPONSOR_DUPLICATE, "disabled", 1, update_modified=True)
		changed = True
	if frappe.db.get_value("Item", SPONSOR_DUPLICATE, "item_group") != LEAF_SPONSORS:
		if frappe.db.exists("Item Group", LEAF_SPONSORS):
			frappe.db.set_value(
				"Item",
				SPONSOR_DUPLICATE,
				"item_group",
				LEAF_SPONSORS,
				update_modified=False,
			)
			changed = True
	if frappe.db.exists("Item", SPONSOR_CANONICAL):
		if int(frappe.db.get_value("Item", SPONSOR_CANONICAL, "disabled") or 0) == 1:
			frappe.db.set_value("Item", SPONSOR_CANONICAL, "disabled", 0, update_modified=True)
			changed = True
		if frappe.db.get_value("Item", SPONSOR_CANONICAL, "item_group") != LEAF_SPONSORS:
			if frappe.db.exists("Item Group", LEAF_SPONSORS):
				frappe.db.set_value(
					"Item",
					SPONSOR_CANONICAL,
					"item_group",
					LEAF_SPONSORS,
					update_modified=False,
				)
				changed = True
	return changed


def sponsors_leaf_item_codes(*, enabled_only: bool = False) -> list[str]:
	if not frappe.db.exists("Item Group", LEAF_SPONSORS):
		return []
	filters: dict[str, Any] = {"item_group": LEAF_SPONSORS}
	if enabled_only:
		filters["disabled"] = 0
	return frappe.get_all("Item", filters=filters, pluck="name", order_by="name")


def run_fix_sponsors_y_ventas() -> dict[str, Any]:
	moved = reassign_expense_specs_from_sponsors()
	dup = disable_duplicate_sponsor_pub()
	remaining = sponsors_leaf_item_codes()
	return {
		"expense_moved": moved,
		"sponsor_pub_disabled": dup,
		"sponsors_remaining": remaining,
	}
