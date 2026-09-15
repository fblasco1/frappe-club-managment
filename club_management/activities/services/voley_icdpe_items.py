"""Consolida aranceles de vóley a ESCUELA + FEDERADO."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.data.voley_aranceles_icdpe import (
	ITEM_VOLEY_ESCUELA,
	ITEM_VOLEY_FEDERADO,
	VOLEY_ITEM_SPECS,
	VOLEY_LEGACY_TO_CANONICAL,
)
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.finance.setup.cleanup_legacy_arancel_items import (
	_activity_link_refs,
	_delete_item_prices,
	_invoice_refs,
	remape_legacy_arancel_links,
)

_CANONICAL_VOLEY = frozenset({ITEM_VOLEY_ESCUELA, ITEM_VOLEY_FEDERADO})


def remap_voley_legacy_links() -> dict[str, Any]:
	"""Reapunta Links de ítems vóley legacy → ESCUELA / FEDERADO."""
	remapped: list[str] = []
	skipped: list[str] = []
	from club_management.finance.setup.cleanup_legacy_arancel_items import (
		_ACTIVITY_LINK_CANDIDATES,
	)

	for legacy, canonical in VOLEY_LEGACY_TO_CANONICAL.items():
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
			for name in frappe.get_all(doctype, filters={field: legacy}, pluck="name"):
				frappe.db.set_value(doctype, name, field, canonical, update_modified=False)
				remapped.append(f"{doctype}:{name}:{field}:{legacy}->{canonical}")
	return {"remapped": remapped, "skipped": skipped}


def disable_legacy_voley_items() -> list[str]:
	"""Deshabilita códigos vóley que no son ESCUELA/FEDERADO."""
	retired: list[str] = []
	for code in sorted(VOLEY_LEGACY_TO_CANONICAL.keys()):
		if code in _CANONICAL_VOLEY:
			continue
		if not frappe.db.exists("Item", code):
			continue
		if int(frappe.db.get_value("Item", code, "disabled") or 0):
			continue
		frappe.db.set_value("Item", code, "disabled", 1, update_modified=True)
		retired.append(code)
	# También cualquier ICDPE-VOLEY-* habilitado que no sea canónico.
	for code in frappe.get_all(
		"Item",
		filters={"name": ["like", "ICDPE-VOLEY-%"], "disabled": 0},
		pluck="name",
		limit_page_length=200,
	):
		if code in _CANONICAL_VOLEY:
			continue
		frappe.db.set_value("Item", code, "disabled", 1, update_modified=True)
		if code not in retired:
			retired.append(code)
	return retired


def delete_disabled_legacy_voley_without_refs() -> dict[str, Any]:
	"""Borra ítems vóley disabled sin facturas ni links de actividad."""
	deleted: list[str] = []
	skipped: list[str] = []
	for code in sorted(VOLEY_LEGACY_TO_CANONICAL.keys()):
		if code in _CANONICAL_VOLEY or not frappe.db.exists("Item", code):
			continue
		if not int(frappe.db.get_value("Item", code, "disabled") or 0):
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
	return {"deleted": deleted, "skipped": skipped}


def remape_voley_sales_invoice_items() -> dict[str, Any]:
	"""Reapunta `Sales Invoice Item.item_code` legacy → ESCUELA / FEDERADO.

	El consolidate anterior remapeaba Links de Actividad/Grupo/Equipo pero no las
	líneas de factura; por eso Deuda por actividad veía arancel Vóley en $0.
	"""
	remapped: list[str] = []
	for legacy, canonical in VOLEY_LEGACY_TO_CANONICAL.items():
		if not frappe.db.exists("Item", canonical):
			continue
		count = int(frappe.db.count("Sales Invoice Item", {"item_code": legacy}) or 0)
		if count <= 0:
			continue
		item_name = frappe.db.get_value("Item", canonical, "item_name") or canonical
		frappe.db.sql(
			"""
			UPDATE "tabSales Invoice Item"
			SET item_code = %s, item_name = %s
			WHERE item_code = %s
			""",
			(canonical, item_name, legacy),
		)
		remapped.append(f"{legacy}->{canonical}:{count}")
	return {"remapped": remapped}


def consolidate_voley_escuela_federado() -> dict[str, Any]:
	"""Crea ESCUELA/FEDERADO, remapea links + facturas, re-seed y retira legacy.

	Spec: ``voley_futbol_aranceles_icdpe.md``.
	"""
	sync_arancel_items(VOLEY_ITEM_SPECS)
	remap_v = remap_voley_legacy_links()
	remap_a = remape_legacy_arancel_links()
	remap_si = remape_voley_sales_invoice_items()
	seed_estructura_actividades_completa(crear_equipos=True)
	# Re-remap por si el seed dejó algo en legacy (no debería).
	remap_v2 = remap_voley_legacy_links()
	retired = disable_legacy_voley_items()
	deleted = delete_disabled_legacy_voley_without_refs()
	return {
		"remap_voley": remap_v,
		"remap_arancel_mensual": remap_a,
		"remap_sales_invoice_items": remap_si,
		"remap_voley_after_seed": remap_v2,
		"retired": retired,
		"deleted": deleted,
	}
