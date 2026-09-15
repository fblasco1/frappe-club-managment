"""Sincroniza ``Item.item_name`` de aranceles al formato canónico.

Spec: ``arancel_item_naming.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.data.arancel_item_spec import format_arancel_mensual_item_name
from club_management.activities.data.basquet_aranceles_icdpe import BASQUET_ITEM_SPECS
from club_management.activities.data.futbol_aranceles_icdpe import FUTBOL_ITEM_SPECS
from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
from club_management.activities.data.voley_aranceles_icdpe import VOLEY_ITEM_SPECS
from club_management.setup.icdpe_create_service_items import _specs


# Residuales habilitados que aún no están en seeds canónicos.
_EXTRA_ITEM_NAMES: dict[str, str] = {
	"ICDPE-ARANCEL-MENSUAL-PATIN-AVANZADO_3": format_arancel_mensual_item_name(
		"PATIN ARTISTICO", "AVANZADO"
	),
}


def expected_arancel_item_names() -> dict[str, str]:
	"""Mapa item_code → item_name oficial (canónicos + placeholders de servicio)."""
	out: dict[str, str] = dict(_EXTRA_ITEM_NAMES)
	for specs in (
		BASQUET_ITEM_SPECS,
		FUTBOL_ITEM_SPECS,
		VOLEY_ITEM_SPECS,
		PATIN_ITEM_SPECS,
		OTRAS_ACTIVIDADES_ITEM_SPECS,
	):
		for spec in specs:
			out[spec.item_code] = spec.item_name
	for spec in _specs():
		if spec.item_code.startswith("ICDPE-ARANCEL-MENSUAL"):
			out[spec.item_code] = spec.item_name
	return out


def sync_arancel_item_names() -> dict[str, Any]:
	"""Actualiza ``item_name`` en Items existentes según el mapa oficial."""
	updated: list[str] = []
	unchanged: list[str] = []
	missing: list[str] = []

	for code, expected_name in sorted(expected_arancel_item_names().items()):
		if not frappe.db.exists("Item", code):
			missing.append(code)
			continue
		current = frappe.db.get_value("Item", code, "item_name") or ""
		if current == expected_name:
			unchanged.append(code)
			continue
		frappe.db.set_value("Item", code, "item_name", expected_name, update_modified=True)
		# description suele espejar el nombre en seeds previos
		if frappe.get_meta("Item").has_field("description"):
			desc = frappe.db.get_value("Item", code, "description") or ""
			if not desc or desc == current:
				frappe.db.set_value("Item", code, "description", expected_name, update_modified=False)
		updated.append(f"{code}:{current}->{expected_name}")

	return {"updated": updated, "unchanged": unchanged, "missing": missing}


def run_sync_arancel_item_names() -> dict[str, Any]:
	return sync_arancel_item_names()
