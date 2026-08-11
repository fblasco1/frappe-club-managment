"""Mueve ítems Funcional al grupo correcto y deshabilita legacy sin uso."""

from __future__ import annotations

import frappe

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	ITEM_FUNCIONAL_1_CLASE,
	ITEM_FUNCIONAL_2_CLASES,
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.finance.setup.icdpe_income_item_groups import (
	LEAF_FUNCIONAL,
	resolve_ingreso_leaf_for_item,
)

_LEGACY_FUNCIONAL_ITEMS: tuple[str, ...] = (
	"ICDPE-ARANCEL-MENSUAL-FUNCIONAL-GAP",
	"ICDPE-ARANCEL-MENSUAL-FUNCIONAL-CROSSFIT",
	"ICDPE-ARANCEL-MENSUAL-FUNCIONAL-PASE_3_CLASES",
	"ICDPE-ARANCEL-MENSUAL-FUNCIONAL-PASE_4_CLASES",
)


def _item_en_uso(item_code: str) -> bool:
	if frappe.db.count("Sales Invoice Item", {"item_code": item_code}):
		return True
	for doctype, field in (
		("Grupo Actividad", "item"),
		("Equipo Actividad", "item"),
		("Actividad", "item"),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).has_field(field):
			continue
		if frappe.db.count(doctype, {field: item_code}):
			return True
	return False


def execute() -> None:
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)

	for code in (ITEM_FUNCIONAL_1_CLASE, ITEM_FUNCIONAL_2_CLASES):
		if not frappe.db.exists("Item", code):
			continue
		leaf = resolve_ingreso_leaf_for_item(code)
		if frappe.db.get_value("Item", code, "item_group") != leaf:
			frappe.db.set_value("Item", code, "item_group", leaf, update_modified=True)

	for code in _LEGACY_FUNCIONAL_ITEMS:
		if not frappe.db.exists("Item", code):
			continue
		# Asegura hoja correcta aunque se deshabilite.
		leaf = resolve_ingreso_leaf_for_item(code) or LEAF_FUNCIONAL
		if frappe.db.get_value("Item", code, "item_group") != leaf:
			frappe.db.set_value("Item", code, "item_group", leaf, update_modified=False)
		if not _item_en_uso(code) and not int(frappe.db.get_value("Item", code, "disabled") or 0):
			frappe.db.set_value("Item", code, "disabled", 1, update_modified=True)
