"""Apaga ítem demo Shoe y elimina aranceles `ICDPE-ARANCEL-MENSUAL-*` deshabilitados.

Spec: ``cleanup_legacy_arancel_items.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

DEMO_SHOE_ITEM_CODE = "138-CMS Shoe"

ARANCEL_MENSUAL_PREFIX = "ICDPE-ARANCEL-MENSUAL-"

# Placeholders / capa actividad que el catálogo oficial puede recrear o reactivar.
KEEP_ARANCEL_MENSUAL_CODES: frozenset[str] = frozenset(
	{
		"ICDPE-ARANCEL-MENSUAL-ACT-funcional",
		"ICDPE-ARANCEL-MENSUAL-ACT-crossfit",
		"ICDPE-ARANCEL-MENSUAL-ACT-zumba",
		"ICDPE-ARANCEL-MENSUAL-futbol",
		"ICDPE-ARANCEL-MENSUAL-voley",
	}
)

# Legacy disabled → canónico oficial (para remapar Links antes de borrar).
LEGACY_ARANCEL_TO_CANONICAL: dict[str, str] = {
	"ICDPE-ARANCEL-MENSUAL-BOXEO-1_VEZ": "ICDPE-BOXEO-1-CLASE",
	"ICDPE-ARANCEL-MENSUAL-BOXEO-2_VECES": "ICDPE-BOXEO-2-CLASES",
	"ICDPE-ARANCEL-MENSUAL-BOXEO-3_VECES": "ICDPE-BOXEO-3-CLASES",
	"ICDPE-ARANCEL-MENSUAL-FUTBOL-GENERAL": "ICDPE-FUTBOL-TABI-A",
	"ICDPE-ARANCEL-MENSUAL-FUTBOL-ESCUELITA": "ICDPE-FUTBOL-TABI-B",
	"ICDPE-ARANCEL-MENSUAL-BASQUET-MINIBASQUET": "ICDPE-BASQUET-MASCULINO-MINIBASQUET",
	"ICDPE-ARANCEL-MENSUAL-BASQUET-FORMATIVAS-AZUL": "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL",
	"ICDPE-ARANCEL-MENSUAL-BASQUET-FORMATIVAS-AMARILLO": "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA",
	"ICDPE-ARANCEL-MENSUAL-BASQUET-FORMATIVAS-MINIBASQUET-FEMENINO": "ICDPE-BASQUET-ESCUELITA",
	"ICDPE-ARANCEL-MENSUAL-basquet-femenino": "ICDPE-BASQUET-FEMENINO-SUP",
	"ICDPE-ARANCEL-MENSUAL-basquet-masculino": "ICDPE-BASQUET-MASCULINO-MINIBASQUET",
}

_ACTIVITY_LINK_CANDIDATES: tuple[tuple[str, str], ...] = (
	("Actividad", "item_arancel"),
	("Actividad", "item"),
	("Grupo Actividad", "item_arancel"),
	("Grupo Actividad", "item"),
	("Equipo Actividad", "item_arancel"),
	("Equipo Actividad", "item"),
	("Cargo Extra", "item"),
	("Cargo Extra Concepto", "item"),
	("Cargo Socio", "item"),
	("Subscription Plan", "item"),
	("Subscription Plan", "item_code"),
)


def disable_demo_shoe() -> dict[str, Any]:
	"""Marca `138-CMS Shoe` como disabled si existe."""
	if not frappe.db.exists("Item", DEMO_SHOE_ITEM_CODE):
		return {"action": "absent"}
	disabled = int(frappe.db.get_value("Item", DEMO_SHOE_ITEM_CODE, "disabled") or 0)
	if disabled:
		return {"action": "already_disabled"}
	frappe.db.set_value("Item", DEMO_SHOE_ITEM_CODE, "disabled", 1, update_modified=True)
	return {"action": "disabled"}


def _invoice_refs(code: str) -> int:
	n = frappe.db.count("Sales Invoice Item", {"item_code": code})
	if frappe.db.exists("DocType", "Purchase Invoice Item"):
		n += frappe.db.count("Purchase Invoice Item", {"item_code": code})
	return n


def _activity_link_refs(code: str) -> int:
	total = 0
	for doctype, field in _ACTIVITY_LINK_CANDIDATES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		if not meta.has_field(field):
			continue
		total += frappe.db.count(doctype, {field: code})
	return total


def remape_legacy_arancel_links() -> dict[str, Any]:
	"""Reapunta Links de aranceles legacy al canónico cuando ambos existen."""
	remapped: list[str] = []
	skipped: list[str] = []

	for legacy, canonical in LEGACY_ARANCEL_TO_CANONICAL.items():
		if not frappe.db.exists("Item", legacy):
			continue
		if not frappe.db.exists("Item", canonical):
			skipped.append(f"{legacy}:missing_canonical={canonical}")
			continue
		for doctype, field in _ACTIVITY_LINK_CANDIDATES:
			if not frappe.db.exists("DocType", doctype):
				continue
			meta = frappe.get_meta(doctype)
			if not meta.has_field(field):
				continue
			names = frappe.get_all(doctype, filters={field: legacy}, pluck="name")
			for name in names:
				frappe.db.set_value(doctype, name, field, canonical, update_modified=False)
				remapped.append(f"{doctype}:{name}:{field}:{legacy}->{canonical}")

	return {"remapped": remapped, "skipped": skipped}


def _delete_item_prices(code: str) -> int:
	deleted = 0
	for name in frappe.get_all("Item Price", filters={"item_code": code}, pluck="name"):
		frappe.delete_doc("Item Price", name, force=1, ignore_permissions=True)
		deleted += 1
	return deleted


def delete_disabled_legacy_arancel_mensual() -> dict[str, Any]:
	"""Borra `ICDPE-ARANCEL-MENSUAL-*` disabled sin uso (salvo KEEP_*)."""
	codes = frappe.get_all(
		"Item",
		filters={"name": ["like", f"{ARANCEL_MENSUAL_PREFIX}%"], "disabled": 1},
		pluck="name",
		limit_page_length=2000,
	)
	deleted: list[str] = []
	skipped: list[str] = []
	kept: list[str] = []

	for code in codes:
		if code in KEEP_ARANCEL_MENSUAL_CODES:
			kept.append(code)
			continue
		inv = _invoice_refs(code)
		if inv:
			skipped.append(f"{code}:invoices={inv}")
			continue
		links = _activity_link_refs(code)
		if links:
			skipped.append(f"{code}:links={links}")
			continue
		try:
			_delete_item_prices(code)
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
			deleted.append(code)
		except Exception as exc:
			skipped.append(f"{code}:{exc.__class__.__name__}")

	return {"deleted": deleted, "skipped": skipped, "kept": kept}


def run_cleanup_legacy_arancel_items() -> dict[str, Any]:
	shoe = disable_demo_shoe()
	remap = remape_legacy_arancel_links()
	aranceles = delete_disabled_legacy_arancel_mensual()
	return {"shoe": shoe, "remap": remap, "aranceles": aranceles}
