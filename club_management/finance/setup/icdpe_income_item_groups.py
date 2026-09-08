"""Jerarquía de Item Groups de ingresos (espejo egresos) + migración.

Pilares ``is_group=1`` → subgrupos (a veces con nivel medio) → Items solo en hojas.
Idempotente. UPDATE SQL sobre ``tabItem.item_group`` (PostgreSQL).
"""

from __future__ import annotations

from typing import Any

import frappe

DEFAULT_ITEM_GROUP_ROOT = "All Item Groups"
LEGACY_ARCHIVE_PARENT = "ICDPE / Legacy ingresos"

# --- Pilares ---
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

# --- Socios (hojas) ---
LEAF_CUOTAS = "Cuotas sociales"
LEAF_CARGOS = "Cargos extras y mora"

# --- Actividades: nivel medio ---
MID_DEPORTES = "Deportes"
MID_FITNESS = "Fitness y actividades"

LEAF_BASQUET = "Básquet"
LEAF_FUTBOL = "Fútbol"
LEAF_VOLEY = "Vóley"
LEAF_PATIN = "Patín"
LEAF_BOXEO = "Boxeo"
LEAF_TAEKWONDO = "Taekwondo"
LEAF_SHUI_LU = "Shui Lu"
LEAF_GIMNASIA = "Gimnasia artística"

LEAF_GIMNASIO = "Gimnasio"
LEAF_FUNCIONAL = "Funcional y CrossFit"
LEAF_YOGA = "Yoga"
LEAF_DANZA = "Danza"
LEAF_RITMOS = "Ritmos latinos"
LEAF_INICIACION = "Iniciación deportiva"

LEAF_FEDERATIVAS = "Cuotas federativas"
LEAF_PUNTUALES = "Actividades puntuales"

# --- Comercial / institucional (hojas) ---
LEAF_ALQUILERES = "Alquileres"
LEAF_GASTRONOMIA = "Gastronomía"
LEAF_SPONSORS = "Sponsors y ventas"
LEAF_ENTRADAS = "Entradas y eventos"
LEAF_SUBSIDIOS = "Subsidios"
LEAF_DONACIONES = "Donaciones"
LEAF_RECAUDACION = "Recaudación institucional"

# Nodos: (name, parent, is_group) en orden de creación (padres antes).
INGRESO_TREE_NODES: tuple[tuple[str, str, int], ...] = (
	(INGRESO_SOCIOS, DEFAULT_ITEM_GROUP_ROOT, 1),
	(LEAF_CUOTAS, INGRESO_SOCIOS, 0),
	(LEAF_CARGOS, INGRESO_SOCIOS, 0),
	(INGRESO_ACTIVIDADES, DEFAULT_ITEM_GROUP_ROOT, 1),
	(MID_DEPORTES, INGRESO_ACTIVIDADES, 1),
	(LEAF_BASQUET, MID_DEPORTES, 0),
	(LEAF_FUTBOL, MID_DEPORTES, 0),
	(LEAF_VOLEY, MID_DEPORTES, 0),
	(LEAF_PATIN, MID_DEPORTES, 0),
	(LEAF_BOXEO, MID_DEPORTES, 0),
	(LEAF_TAEKWONDO, MID_DEPORTES, 0),
	(LEAF_SHUI_LU, MID_DEPORTES, 0),
	(LEAF_GIMNASIA, MID_DEPORTES, 0),
	(MID_FITNESS, INGRESO_ACTIVIDADES, 1),
	(LEAF_GIMNASIO, MID_FITNESS, 0),
	(LEAF_FUNCIONAL, MID_FITNESS, 0),
	(LEAF_YOGA, MID_FITNESS, 0),
	(LEAF_DANZA, MID_FITNESS, 0),
	(LEAF_RITMOS, MID_FITNESS, 0),
	(LEAF_INICIACION, MID_FITNESS, 0),
	(LEAF_FEDERATIVAS, INGRESO_ACTIVIDADES, 0),
	(LEAF_PUNTUALES, INGRESO_ACTIVIDADES, 0),
	(INGRESO_COMERCIALES, DEFAULT_ITEM_GROUP_ROOT, 1),
	(LEAF_ALQUILERES, INGRESO_COMERCIALES, 0),
	(LEAF_GASTRONOMIA, INGRESO_COMERCIALES, 0),
	(LEAF_SPONSORS, INGRESO_COMERCIALES, 0),
	(LEAF_ENTRADAS, INGRESO_COMERCIALES, 0),
	(INGRESO_INSTITUCIONALES, DEFAULT_ITEM_GROUP_ROOT, 1),
	(LEAF_SUBSIDIOS, INGRESO_INSTITUCIONALES, 0),
	(LEAF_DONACIONES, INGRESO_INSTITUCIONALES, 0),
	(LEAF_RECAUDACION, INGRESO_INSTITUCIONALES, 0),
)

INGRESO_LEAF_GROUPS: tuple[str, ...] = tuple(n for n, _p, isg in INGRESO_TREE_NODES if isg == 0)

# Códigos explícitos → hoja
ITEM_TO_LEAF: dict[str, str] = {
	"ICDPE-CUOTA-SOCIAL": LEAF_CUOTAS,
	"ICDPE-INSCRIPCION": LEAF_CUOTAS,
	"ICDPE-MULTA": LEAF_CARGOS,
	"ICDPE-CARGO-VARIOS": LEAF_CARGOS,
	"RECARGO-MORA": LEAF_CARGOS,
	"ICDPE-COLONIAS": LEAF_PUNTUALES,
	"ICDPE-EVENTOS": LEAF_PUNTUALES,
	"ICDPE-FIN-ENTRADAS": LEAF_ENTRADAS,
	"ICDPE-FIN-ALQUILER-TEMP": LEAF_ALQUILERES,
	"ICDPE-FIN-BUFFET": LEAF_GASTRONOMIA,
	"ICDPE-FIN-RESTAURANTE": LEAF_GASTRONOMIA,
	"ICDPE-FIN-CANON-CONCESION": LEAF_GASTRONOMIA,
	"ICDPE-POS-BUFFET": LEAF_GASTRONOMIA,
	"ICDPE-POS-RESTAURANTE": LEAF_GASTRONOMIA,
	"ICDPE-POS-PENA-ROCK": LEAF_GASTRONOMIA,
	"ICDPE-FIN-SPONSOR": LEAF_SPONSORS,
	"ICDPE-SPONSOR-PUB": LEAF_SPONSORS,
	"ICDPE-FIN-INDUMENTARIA": LEAF_SPONSORS,
	"ICDPE-VENTA-INDUMENTARIA": LEAF_SPONSORS,
	"ICDPE-FIN-SUBSIDIO": LEAF_SUBSIDIOS,
	"ICDPE-FIN-DONACION": LEAF_DONACIONES,
	"ICDPE-FIN-EVENTO-RECAUDACION": LEAF_RECAUDACION,
	"ICDPE-DANZA": LEAF_DANZA,
	"ICDPE-RITMOS-LATINOS": LEAF_RITMOS,
	"ICDPE-SHUI-LU": LEAF_SHUI_LU,
	"ICDPE-TAEKWONDO": LEAF_TAEKWONDO,
	"ICDPE-ARANCEL-MENSUAL-FITNESS-MUSC": LEAF_GIMNASIO,
}

# Prefijos (orden: más específico primero)
PREFIX_TO_LEAF: tuple[tuple[str, str], ...] = (
	("ICDPE-CUOTA-FEDERATIVA-", LEAF_FEDERATIVAS),
	("ICDPE-BASQUET-", LEAF_BASQUET),
	("ICDPE-FUTBOL-", LEAF_FUTBOL),
	("ICDPE-VOLEY-", LEAF_VOLEY),
	("ICDPE-PATIN-", LEAF_PATIN),
	("ICDPE-BOXEO-", LEAF_BOXEO),
	("ICDPE-GIMNASIA-ARTISTICA-", LEAF_GIMNASIA),
	("ICDPE-GYM-", LEAF_GIMNASIO),
	("ICDPE-YOGA-", LEAF_YOGA),
	("ICDPE-INICIACION-DEPORTIVA-", LEAF_INICIACION),
	("ICDPE-FUNCIONAL-", LEAF_FUNCIONAL),
	("ICDPE-ALQ-", LEAF_ALQUILERES),
	("ICDPE-ARANCEL-MENSUAL-basquet", LEAF_BASQUET),
	("ICDPE-ARANCEL-MENSUAL-BASQUET", LEAF_BASQUET),
	("ICDPE-ARANCEL-MENSUAL-futbol", LEAF_FUTBOL),
	("ICDPE-ARANCEL-MENSUAL-FUTBOL", LEAF_FUTBOL),
	("ICDPE-ARANCEL-MENSUAL-voley", LEAF_VOLEY),
	("ICDPE-ARANCEL-MENSUAL-VOLEY", LEAF_VOLEY),
	("ICDPE-ARANCEL-MENSUAL-patin", LEAF_PATIN),
	("ICDPE-ARANCEL-MENSUAL-PATIN", LEAF_PATIN),
	("ICDPE-ARANCEL-MENSUAL-boxeo", LEAF_BOXEO),
	("ICDPE-ARANCEL-MENSUAL-BOXEO", LEAF_BOXEO),
	("ICDPE-ARANCEL-MENSUAL-taekwondo", LEAF_TAEKWONDO),
	("ICDPE-ARANCEL-MENSUAL-TAEKWONDO", LEAF_TAEKWONDO),
	("ICDPE-ARANCEL-MENSUAL-shui", LEAF_SHUI_LU),
	("ICDPE-ARANCEL-MENSUAL-SHUI", LEAF_SHUI_LU),
	("ICDPE-ARANCEL-MENSUAL-gimnasia", LEAF_GIMNASIA),
	("ICDPE-ARANCEL-MENSUAL-GIMNASIA", LEAF_GIMNASIA),
	("ICDPE-ARANCEL-MENSUAL-DANZA", LEAF_DANZA),
	("ICDPE-ARANCEL-MENSUAL-YOGA", LEAF_YOGA),
	("ICDPE-ARANCEL-MENSUAL-RITMOS", LEAF_RITMOS),
	("ICDPE-ARANCEL-MENSUAL-INICIACION", LEAF_INICIACION),
	("ICDPE-ARANCEL-MENSUAL-FUNCIONAL", LEAF_FUNCIONAL),
	("ICDPE-ARANCEL-MENSUAL-FITNESS", LEAF_GIMNASIO),
	("ICDPE-ARANCEL-MENSUAL-GIMNASIO", LEAF_GIMNASIO),
	("ICDPE-ARANCEL-MENSUAL-ACT-danza", LEAF_DANZA),
	("ICDPE-ARANCEL-MENSUAL-ACT-yoga", LEAF_YOGA),
	("ICDPE-ARANCEL-MENSUAL-ACT-crossfit", LEAF_FUNCIONAL),
	("ICDPE-ARANCEL-MENSUAL-ACT-funcional", LEAF_FUNCIONAL),
	("ICDPE-ARANCEL-MENSUAL-ACT-ritmos", LEAF_RITMOS),
	("ICDPE-ARANCEL-MENSUAL-ACT-zumba", LEAF_RITMOS),
	("ICDPE-ARANCEL-MENSUAL-ACT-iniciacion", LEAF_INICIACION),
	("ICDPE-ARANCEL-MENSUAL-ACT-", LEAF_INICIACION),
)

# Compat: mapeos legacy planos (fase previa) → se re-migran a hojas
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

INCOME_ITEM_TO_PILLAR: dict[str, str] = {
	code: (
		INGRESO_INSTITUCIONALES
		if leaf in (LEAF_SUBSIDIOS, LEAF_DONACIONES, LEAF_RECAUDACION)
		else INGRESO_COMERCIALES
		if leaf in (LEAF_ALQUILERES, LEAF_GASTRONOMIA, LEAF_SPONSORS, LEAF_ENTRADAS)
		else INGRESO_SOCIOS
		if leaf in (LEAF_CUOTAS, LEAF_CARGOS)
		else INGRESO_ACTIVIDADES
	)
	for code, leaf in ITEM_TO_LEAF.items()
	if code.startswith("ICDPE-FIN-")
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


def resolve_ingreso_leaf_for_item(item_code: str) -> str:
	"""Resuelve la hoja de Item Group para un código de Item de ingreso.

	No asume que todo ``ICDPE-FIN-*`` es ingreso: los egresos del catálogo
	financiero se omiten en la reasignación de ingresos y tienen hoja propia
	en ``EXPENSE_SPECS``.
	"""
	if item_code in ITEM_TO_LEAF:
		return ITEM_TO_LEAF[item_code]
	upper = item_code
	for prefix, leaf in PREFIX_TO_LEAF:
		if upper.startswith(prefix) or upper.upper().startswith(prefix.upper()):
			return leaf
	if upper.startswith("ICDPE-ARANCEL-MENSUAL"):
		return LEAF_INICIACION
	# Prefijo FIN sin mapeo explícito: no empujar a Sponsors (evita tragar egresos).
	if upper.startswith("ICDPE-FIN-"):
		return LEAF_CARGOS
	return LEAF_CARGOS


def _ensure_item_group(name: str, *, parent: str, is_group: int = 0) -> None:
	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		changed = False
		if int(doc.is_group or 0) != int(is_group):
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
	"""Crea / alinea el árbol. Si un padre aún es hoja (tiene Items), cuelga hijos en raíz temporalmente."""
	if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
		frappe.throw(f"No existe el Item Group raíz '{DEFAULT_ITEM_GROUP_ROOT}'")

	for name, parent, is_group in INGRESO_TREE_NODES:
		actual_parent = parent
		if parent != DEFAULT_ITEM_GROUP_ROOT and frappe.db.exists("Item Group", parent):
			if int(frappe.db.get_value("Item Group", parent, "is_group") or 0) == 0:
				actual_parent = DEFAULT_ITEM_GROUP_ROOT
		elif parent != DEFAULT_ITEM_GROUP_ROOT and not frappe.db.exists("Item Group", parent):
			# Crear padre como nodo (sin ítems) en el mismo pase ordenado
			_ensure_item_group(parent, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=1)
			actual_parent = parent

		create_isg = is_group
		if (
			is_group == 1
			and frappe.db.exists("Item Group", name)
			and frappe.db.count("Item", {"item_group": name})
			and not frappe.db.count("Item Group", {"parent_item_group": name})
		):
			# Solo mantener como hoja temporal si aún no tiene subgrupos.
			create_isg = 0
		_ensure_item_group(name, parent=actual_parent, is_group=create_isg)


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


def _is_expense_catalog_item(item_code: str) -> bool:
	"""True si el ítem pertenece al catálogo de egresos (no reasignar como ingreso)."""
	from club_management.finance.setup.icdpe_finance_items import EXPENSE_SPECS

	if item_code in {s.item_code for s in EXPENSE_SPECS}:
		return True
	if not frappe.db.exists("Item", item_code):
		return False
	row = frappe.db.get_value(
		"Item",
		item_code,
		["is_purchase_item", "is_sales_item"],
		as_dict=True,
	)
	if not row:
		return False
	return bool(int(row.is_purchase_item or 0) and not int(row.is_sales_item or 0))


def _move_all_items_from_group(old_group: str) -> int:
	"""Mueve cada Item del grupo viejo a su hoja resuelta (omite egresos)."""
	if not frappe.db.exists("Item Group", old_group):
		return 0
	codes = frappe.get_all("Item", filters={"item_group": old_group}, pluck="name")
	n = 0
	by_leaf: dict[str, list[str]] = {}
	for code in codes:
		if _is_expense_catalog_item(code):
			continue
		leaf = resolve_ingreso_leaf_for_item(code)
		by_leaf.setdefault(leaf, []).append(code)
	for leaf, leaf_codes in by_leaf.items():
		n += _update_item_codes_group(leaf_codes, leaf)
	return n


def reassign_income_items_to_leaves() -> dict[str, int]:
	"""Reasigna Items desde pilares planos / grupos legacy hacia hojas."""
	ensure_ingresos_item_group_tree()
	counts: dict[str, int] = {}

	# 1) Explícitos
	by_leaf: dict[str, list[str]] = {}
	for code, leaf in ITEM_TO_LEAF.items():
		by_leaf.setdefault(leaf, []).append(code)
	for leaf, codes in by_leaf.items():
		n = _update_item_codes_group(codes, leaf)
		counts[leaf] = counts.get(leaf, 0) + n

	# 2) Todo lo que aún esté en un pilar (fase plana)
	for pillar in INGRESO_PILLARS:
		counts[pillar] = counts.get(pillar, 0) + _move_all_items_from_group(pillar)

	# 3) Grupos ICDPE / legacy
	for old in LEGACY_INCOME_GROUPS_TO_CLEAN:
		counts[old] = counts.get(old, 0) + _move_all_items_from_group(old)

	# 4) Prefijos: cualquier ICDPE-* habilitado aún fuera de hojas (sin egresos)
	leaf_set = set(INGRESO_LEAF_GROUPS)
	strays = frappe.get_all(
		"Item",
		filters={"name": ["like", "ICDPE-%"], "disabled": 0},
		pluck="name",
	)
	strays += frappe.get_all("Item", filters={"name": "RECARGO-MORA"}, pluck="name")
	to_move: dict[str, list[str]] = {}
	for code in strays:
		if _is_expense_catalog_item(code):
			continue
		cur = frappe.db.get_value("Item", code, "item_group")
		if cur in leaf_set:
			continue
		leaf = resolve_ingreso_leaf_for_item(code)
		to_move.setdefault(leaf, []).append(code)
	for leaf, codes in to_move.items():
		n = _update_item_codes_group(codes, leaf)
		counts[leaf] = counts.get(leaf, 0) + n

	return counts


def promote_ingreso_pillars_to_groups() -> list[str]:
	"""Tras vaciar pilares, set is_group=1 según INGRESO_TREE_NODES."""
	promoted: list[str] = []
	for name, parent, is_group in INGRESO_TREE_NODES:
		if not frappe.db.exists("Item Group", name):
			continue
		if int(is_group) != 1:
			_ensure_item_group(name, parent=parent, is_group=0)
			continue
		n_items = frappe.db.count("Item", {"item_group": name})
		if n_items:
			continue
		_ensure_item_group(name, parent=parent, is_group=1)
		promoted.append(name)
	return promoted


def cleanup_legacy_income_groups() -> dict[str, Any]:
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
			_ensure_item_group(LEGACY_ARCHIVE_PARENT, parent=DEFAULT_ITEM_GROUP_ROOT, is_group=1)
		try:
			doc = frappe.get_doc("Item Group", name)
			if doc.parent_item_group != LEGACY_ARCHIVE_PARENT:
				doc.parent_item_group = LEGACY_ARCHIVE_PARENT
				doc.save(ignore_permissions=True)
		except Exception as exc2:
			skipped.append(f"{name}:archive_failed:{exc2.__class__.__name__}")

	return {"deleted": deleted, "archived": archived, "skipped": skipped}


def run_ingresos_item_groups_migration() -> dict[str, Any]:
	"""Pipeline completo: árbol → hojas → promover pilares → cleanup legacy."""
	ensure_ingresos_item_group_tree()
	moved = reassign_income_items_to_leaves()
	promoted = promote_ingreso_pillars_to_groups()
	# Re-asegurar padres/is_group finales
	ensure_ingresos_item_group_tree()
	promote_ingreso_pillars_to_groups()
	cleanup = cleanup_legacy_income_groups()
	return {"moved": moved, "promoted": promoted, "cleanup": cleanup}


# Alias usados por seeds previos
reassign_income_items = reassign_income_items_to_leaves
