"""4 pilares de Item Group para ingresos + migración desde grupos ICDPE / *.

Idempotente. Usa UPDATE SQL (PostgreSQL) para reasignar ``tabItem.item_group``.
"""

from __future__ import annotations

from typing import Any

import frappe

DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"
LEGACY_ARCHIVE_PARENT = "ICDPE / Legacy ingresos"

INGRESO_SOCIOS = "Ingresos de Socios y Membresías"
INGRESO_ACTIVIDADES = "Ingresos por Actividades Deportivas"
INGRESO_COMERCIALES = "Ingresos Comerciales y Alquileres"
INGRESO_INSTITUCIONALES = "Ingresos Institucionales"

INGRESO_PILLARS: tuple[str, ...] = (
	INGRESO_SOCIOS,
	INGRESO_ACTIVIDADES,
	INGRESO_COMERCIALES,
	INGRESO_INSTITUCIONALES,
)

# Grupo viejo → pilar (bulk por item_group).
LEGACY_INCOME_GROUP_TO_PILLAR: dict[str, str] = {
	"ICDPE / Cuotas y membresías": INGRESO_SOCIOS,
	"ICDPE / Cargos varios": INGRESO_SOCIOS,
	"ICDPE / Aranceles deportes": INGRESO_ACTIVIDADES,
	"ICDPE / Aranceles fitness": INGRESO_ACTIVIDADES,
	"ICDPE / Aranceles actividades": INGRESO_ACTIVIDADES,
	"ICDPE / Federaciones deportes": INGRESO_ACTIVIDADES,
	"ICDPE / Actividades puntuales": INGRESO_ACTIVIDADES,
	"ICDPE / Alquileres": INGRESO_COMERCIALES,
	"ICDPE / Comercial": INGRESO_COMERCIALES,
	"ICDPE / Gastronomía POS": INGRESO_COMERCIALES,
}

# Overrides por código (parte de ICDPE / Finanzas ingresos se parte en 2 pilares).
INCOME_ITEM_TO_PILLAR: dict[str, str] = {
	"ICDPE-FIN-ENTRADAS": INGRESO_COMERCIALES,
	"ICDPE-FIN-ALQUILER-TEMP": INGRESO_COMERCIALES,
	"ICDPE-FIN-BUFFET": INGRESO_COMERCIALES,
	"ICDPE-FIN-RESTAURANTE": INGRESO_COMERCIALES,
	"ICDPE-FIN-CANON-CONCESION": INGRESO_COMERCIALES,
	"ICDPE-FIN-SPONSOR": INGRESO_COMERCIALES,
	"ICDPE-FIN-INDUMENTARIA": INGRESO_COMERCIALES,
	"ICDPE-FIN-SUBSIDIO": INGRESO_INSTITUCIONALES,
	"ICDPE-FIN-DONACION": INGRESO_INSTITUCIONALES,
	"ICDPE-FIN-EVENTO-RECAUDACION": INGRESO_INSTITUCIONALES,
}

LEGACY_INCOME_GROUPS_TO_CLEAN: tuple[str, ...] = tuple(
	sorted(
		{
			*LEGACY_INCOME_GROUP_TO_PILLAR.keys(),
			"ICDPE / Finanzas ingresos",
			"ICDPE / Packs deportes",
			"ICDPE / Packs actividades",
			"ICDPE / Packs fitness",
		}
	)
)


def _ensure_item_group(name: str, *, parent: str, is_group: int = 0) -> None:
	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		changed = False
		if int(doc.is_group or 0) != int(is_group):
			# No promover a grupo si aún tiene Items.
			if int(is_group) == 1 and frappe.db.count("Item", {"item_group": name}):
				pass
			else:
				doc.is_group = is_group
				changed = True
		if parent and doc.parent_item_group != parent:
			doc.parent_item_group = parent
			changed = True
		if changed:
			doc.save(ignore_permissions=True)
		return

	if parent and not frappe.db.exists("Item Group", parent):
		frappe.throw(f"No existe el Item Group padre '{parent}'")

	frappe.get_doc(
		{
			"doctype": "Item Group",
			"item_group_name": name,
			"parent_item_group": parent,
			"is_group": is_group,
		}
	).insert(ignore_permissions=True)


def ensure_ingresos_item_group_tree() -> None:
	"""Crea los 4 pilares bajo All Item Groups (hoja: reciben Items)."""
	if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
		frappe.throw(f"No existe el Item Group raíz '{DEFAULT_ITEM_GROUP_ROOT}'")
	for pillar in INGRESO_PILLARS:
		_ensure_item_group(pillar, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=0)


def _update_items_group(old_group: str, new_group: str) -> int:
	"""UPDATE masivo PostgreSQL/compatible vía frappe.db.sql."""
	if not frappe.db.exists("Item Group", old_group):
		return 0
	if old_group == new_group:
		return 0
	frappe.db.sql(
		"""
		UPDATE "tabItem"
		SET item_group = %s
		WHERE item_group = %s
		""",
		(new_group, old_group),
	)
	return int(frappe.db.sql(
		"""
		SELECT COUNT(*) FROM "tabItem" WHERE item_group = %s
		""",
		(new_group,),
	)[0][0] or 0)


def _update_item_codes_group(item_codes: list[str], new_group: str) -> int:
	if not item_codes:
		return 0
	existing = [c for c in item_codes if frappe.db.exists("Item", c)]
	if not existing:
		return 0
	placeholders = ", ".join(["%s"] * len(existing))
	frappe.db.sql(
		f"""
		UPDATE "tabItem"
		SET item_group = %s
		WHERE name IN ({placeholders})
		""",
		tuple([new_group, *existing]),
	)
	return len(existing)


def reassign_income_items() -> dict[str, int]:
	"""Reasigna Items a los 4 pilares. Devuelve contadores por destino."""
	ensure_ingresos_item_group_tree()
	counts: dict[str, int] = {p: 0 for p in INGRESO_PILLARS}

	# 1) Overrides por código (antes del bulk por grupo viejo).
	by_pillar: dict[str, list[str]] = {p: [] for p in INGRESO_PILLARS}
	for code, pillar in INCOME_ITEM_TO_PILLAR.items():
		by_pillar[pillar].append(code)
	for pillar, codes in by_pillar.items():
		n = _update_item_codes_group(codes, pillar)
		counts[pillar] = counts.get(pillar, 0) + n

	# 2) Bulk por grupo legacy.
	for old_group, pillar in LEGACY_INCOME_GROUP_TO_PILLAR.items():
		before = frappe.db.count("Item", {"item_group": old_group})
		if before:
			_update_items_group(old_group, pillar)
			counts[pillar] = counts.get(pillar, 0) + before

	# 3) Remanentes de Finanzas ingresos → Comercial (fallback).
	fin = "ICDPE / Finanzas ingresos"
	rem = frappe.db.count("Item", {"item_group": fin})
	if rem:
		_update_items_group(fin, INGRESO_COMERCIALES)
		counts[INGRESO_COMERCIALES] = counts.get(INGRESO_COMERCIALES, 0) + rem

	return counts


def cleanup_legacy_income_groups() -> dict[str, Any]:
	"""Elimina grupos ICDPE / de ingreso vacíos; si hay vínculo, archiva."""
	deleted: list[str] = []
	archived: list[str] = []
	skipped: list[str] = []

	for name in LEGACY_INCOME_GROUPS_TO_CLEAN:
		if not frappe.db.exists("Item Group", name):
			continue
		n_items = frappe.db.count("Item", {"item_group": name})
		if n_items:
			skipped.append(f"{name}:still_has_{n_items}_items")
			continue
		try:
			frappe.delete_doc("Item Group", name, ignore_permissions=True, force=1)
			deleted.append(name)
			continue
		except Exception as exc:
			archived.append(f"{name}:{exc.__class__.__name__}")

		if not frappe.db.exists("Item Group", LEGACY_ARCHIVE_PARENT):
			_ensure_item_group(
				LEGACY_ARCHIVE_PARENT,
				parent=DEFAULT_ITEM_GROUP_ROOT,
				is_group=1,
			)
		try:
			doc = frappe.get_doc("Item Group", name)
			if doc.parent_item_group != LEGACY_ARCHIVE_PARENT:
				doc.parent_item_group = LEGACY_ARCHIVE_PARENT
				doc.save(ignore_permissions=True)
		except Exception as exc2:
			skipped.append(f"{name}:archive_failed:{exc2.__class__.__name__}")

	return {"deleted": deleted, "archived": archived, "skipped": skipped}


def run_ingresos_item_groups_migration() -> dict[str, Any]:
	"""Pipeline: pilares → reasignar → limpiar grupos viejos."""
	ensure_ingresos_item_group_tree()
	moved = reassign_income_items()
	cleanup = cleanup_legacy_income_groups()
	return {"moved": moved, "cleanup": cleanup}
