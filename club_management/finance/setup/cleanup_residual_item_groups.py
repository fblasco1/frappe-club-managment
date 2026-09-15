"""Limpieza de Item Groups residuales planos bajo All Item Groups.

Spec: ``cleanup_residual_item_groups.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.finance.setup.icdpe_finance_items import (
	DEFAULT_ITEM_GROUP_ROOT,
	GROUP_FEDERATIVOS,
	GROUP_HONORARIOS,
	GROUP_IMPUESTOS,
	GROUP_INSUMOS,
	GROUP_OBRAS,
	GROUP_REMUNERACIONES,
	GROUP_REPARACIONES,
	GROUP_SEGUROS,
	ensure_egresos_item_group_tree,
)
from club_management.finance.setup.icdpe_income_item_groups import (
	LEAF_CUOTAS,
	ensure_ingresos_item_group_tree,
)

RESIDUAL_FINANZAS_EGRESOS = "ICDPE / Finanzas egresos"
RESIDUAL_CUOTAS_SOCIALES = "Cuotas Sociales"  # distinto de LEAF_CUOTAS («Cuotas sociales»)

# Ítems legacy disabled del catálogo plano → hoja de egreso canónica.
LEGACY_EXPENSE_ITEM_TO_LEAF: dict[str, str] = {
	"ICDPE-FIN-SUELDOS": GROUP_REMUNERACIONES,
	"ICDPE-FIN-IMPUESTOS": GROUP_IMPUESTOS,
	"ICDPE-FIN-FEDERACION": GROUP_FEDERATIVOS,
	"ICDPE-FIN-INSUMOS-DEP": GROUP_INSUMOS,
	"ICDPE-FIN-MANT-IMPLEMENTOS": GROUP_REPARACIONES,
	"ICDPE-FIN-MANT-INSTALACIONES": GROUP_REPARACIONES,
	"ICDPE-FIN-OBRAS": GROUP_OBRAS,
	"ICDPE-FIN-ENTRENADORES": GROUP_HONORARIOS,
	"ICDPE-FIN-ARBITROS": GROUP_HONORARIOS,
	"ICDPE-FIN-VIATICOS": GROUP_HONORARIOS,
	"ICDPE-FIN-SEGURIDAD": GROUP_SEGUROS,
}

RESIDUAL_GROUPS_TO_DELETE_IF_EMPTY: tuple[str, ...] = (
	RESIDUAL_FINANZAS_EGRESOS,
	RESIDUAL_CUOTAS_SOCIALES,
)


def _update_items_group(item_codes: list[str], new_group: str) -> int:
	if not item_codes or not frappe.db.exists("Item Group", new_group):
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


def reassign_legacy_expense_items_to_leaves() -> dict[str, int]:
	"""Mueve ítems del residual Finanzas egresos (u otros) a hojas canónicas."""
	ensure_egresos_item_group_tree()
	counts: dict[str, int] = {}
	by_leaf: dict[str, list[str]] = {}
	for code, leaf in LEGACY_EXPENSE_ITEM_TO_LEAF.items():
		by_leaf.setdefault(leaf, []).append(code)
	for leaf, codes in by_leaf.items():
		n = _update_items_group(codes, leaf)
		if n:
			counts[leaf] = counts.get(leaf, 0) + n

	# Cualquier otro Item aún en el residual → Honorarios (cajón de legacy disabled).
	if frappe.db.exists("Item Group", RESIDUAL_FINANZAS_EGRESOS):
		strays = frappe.get_all(
			"Item",
			filters={"item_group": RESIDUAL_FINANZAS_EGRESOS},
			pluck="name",
		)
		known = set(LEGACY_EXPENSE_ITEM_TO_LEAF)
		extra = [c for c in strays if c not in known]
		if extra:
			n = _update_items_group(extra, GROUP_HONORARIOS)
			counts[GROUP_HONORARIOS] = counts.get(GROUP_HONORARIOS, 0) + n
	return counts


def reassign_residual_cuotas_sociales() -> int:
	"""Mueve ítems del residual «Cuotas Sociales» a la hoja «Cuotas sociales»."""
	ensure_ingresos_item_group_tree()
	if not frappe.db.exists("Item Group", RESIDUAL_CUOTAS_SOCIALES):
		return 0
	if RESIDUAL_CUOTAS_SOCIALES == LEAF_CUOTAS:
		return 0
	codes = frappe.get_all(
		"Item",
		filters={"item_group": RESIDUAL_CUOTAS_SOCIALES},
		pluck="name",
	)
	return _update_items_group(codes, LEAF_CUOTAS)


def delete_empty_residual_groups() -> dict[str, Any]:
	deleted: list[str] = []
	skipped: list[str] = []
	for name in RESIDUAL_GROUPS_TO_DELETE_IF_EMPTY:
		if not frappe.db.exists("Item Group", name):
			continue
		# No borrar la hoja canónica de ingresos si algún día coincidiera el name.
		if name == LEAF_CUOTAS:
			skipped.append(f"{name}:is_canonical_leaf")
			continue
		n_items = frappe.db.count("Item", {"item_group": name})
		if n_items:
			skipped.append(f"{name}:still_has_{n_items}_items")
			continue
		try:
			frappe.delete_doc("Item Group", name, ignore_permissions=True, force=1)
			deleted.append(name)
		except Exception as exc:
			skipped.append(f"{name}:{exc.__class__.__name__}")
	return {"deleted": deleted, "skipped": skipped}


def run_cleanup_residual_item_groups() -> dict[str, Any]:
	"""Pipeline: reasignar egresos/cuotas → borrar grupos residuales vacíos."""
	expense_moved = reassign_legacy_expense_items_to_leaves()
	cuotas_moved = reassign_residual_cuotas_sociales()
	cleanup = delete_empty_residual_groups()
	return {
		"expense_moved": expense_moved,
		"cuotas_moved": cuotas_moved,
		"cleanup": cleanup,
	}
