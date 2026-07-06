"""Consolida CC ERPNext de básquet (3 legacy → 1 unificado). Spec: basquet_cost_center_consolidado.md."""

from __future__ import annotations

import frappe

from club_management.setup.basquet_cost_center import (
	BASQUET_COST_CENTER,
	BASQUET_COST_CENTER_NAME,
	BASQUET_COST_CENTER_PARENT,
	LEGACY_BASQUET_COST_CENTERS,
)
from club_management.setup.icdpe_company import resolve_icdpe_company


def ensure_basquet_unified_cost_center() -> str:
	"""Crea el CC unificado si no existe. Devuelve el `name` del Cost Center."""
	if frappe.db.exists("Cost Center", BASQUET_COST_CENTER):
		return BASQUET_COST_CENTER

	if not frappe.db.exists("Cost Center", BASQUET_COST_CENTER_PARENT):
		frappe.throw(
			f"Falta el CC padre {BASQUET_COST_CENTER_PARENT!r} para crear {BASQUET_COST_CENTER!r}."
		)

	frappe.get_doc(
		{
			"doctype": "Cost Center",
			"cost_center_name": BASQUET_COST_CENTER_NAME,
			"parent_cost_center": BASQUET_COST_CENTER_PARENT,
			"company": resolve_icdpe_company(),
			"is_group": 0,
		}
	).insert(ignore_permissions=True)
	return BASQUET_COST_CENTER


def _item_default_rows_for_cost_centers(cost_centers: tuple[str, ...]) -> list[dict[str, str]]:
	rows: list[dict[str, str]] = []
	for cc in cost_centers:
		for row in frappe.get_all(
			"Item Default",
			filters={"selling_cost_center": cc},
			fields=["name", "parent"],
		):
			rows.append({"item_code": row["parent"], "row_name": row["name"]})
	return rows


def _reassign_item_defaults_to_basquet_cc() -> list[str]:
	updated: list[str] = []
	for row in _item_default_rows_for_cost_centers(LEGACY_BASQUET_COST_CENTERS):
		frappe.db.set_value(
			"Item Default",
			row.row_name,
			"selling_cost_center",
			BASQUET_COST_CENTER,
			update_modified=False,
		)
		updated.append(row.item_code)
	return updated


def _disable_legacy_basquet_cost_centers() -> list[str]:
	disabled: list[str] = []
	for cc in LEGACY_BASQUET_COST_CENTERS:
		if not frappe.db.exists("Cost Center", cc):
			continue
		if frappe.db.get_value("Cost Center", cc, "disabled"):
			continue
		frappe.db.set_value("Cost Center", cc, "disabled", 1, update_modified=True)
		disabled.append(cc)
	return disabled


def consolidate_basquet_cost_centers(*, disable_legacy: bool = True) -> dict[str, list[str] | str]:
	"""Reasigna ítems al CC unificado y opcionalmente deshabilita CC legacy."""
	ensure_basquet_unified_cost_center()
	items_updated = _reassign_item_defaults_to_basquet_cc()
	legacy_disabled: list[str] = []
	if disable_legacy:
		legacy_disabled = _disable_legacy_basquet_cost_centers()
	return {
		"cost_center": BASQUET_COST_CENTER,
		"items_updated": items_updated,
		"legacy_disabled": legacy_disabled,
	}


def execute() -> dict[str, list[str] | str]:
	return consolidate_basquet_cost_centers()
