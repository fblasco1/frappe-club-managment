"""Aplana Main y renombra hojas de Cost Center ICDPE (sin prefijo de área).

Spec: ``cost_centers_aplanar_renombrar.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.setup.icdpe_company import COMPANY_ABBR, resolve_icdpe_company

MAIN_CC = f"Main - {COMPANY_ABBR}"

# old_name → new_name (document name = cost_center_name + " - " + abbr)
COST_CENTER_RENAME_MAP: tuple[tuple[str, str], ...] = (
	(f"Deportes - Futbol - {COMPANY_ABBR}", f"Futbol - {COMPANY_ABBR}"),
	(f"Deportes - Basquet - {COMPANY_ABBR}", f"Basquet - {COMPANY_ABBR}"),
	(f"Deportes - Voley - {COMPANY_ABBR}", f"Voley - {COMPANY_ABBR}"),
	(f"Deportes - Patin - {COMPANY_ABBR}", f"Patin - {COMPANY_ABBR}"),
	(f"Deportes - Boxeo - {COMPANY_ABBR}", f"Boxeo - {COMPANY_ABBR}"),
	(f"Deportes - Gimnasia Artistica - {COMPANY_ABBR}", f"Gimnasia Artistica - {COMPANY_ABBR}"),
	(f"Deportes - Taekwondo - {COMPANY_ABBR}", f"Taekwondo - {COMPANY_ABBR}"),
	(f"Deportes - Shui Lu - {COMPANY_ABBR}", f"Shui Lu - {COMPANY_ABBR}"),
	(f"Actividades - Iniciacion Deportiva - {COMPANY_ABBR}", f"Iniciacion Deportiva - {COMPANY_ABBR}"),
	(f"Actividades - Danza - {COMPANY_ABBR}", f"Danza - {COMPANY_ABBR}"),
	(f"Actividades - Yoga - {COMPANY_ABBR}", f"Yoga - {COMPANY_ABBR}"),
	(f"Actividades - CrossFit - {COMPANY_ABBR}", f"CrossFit - {COMPANY_ABBR}"),
	(f"Actividades - Funcional - {COMPANY_ABBR}", f"Funcional - {COMPANY_ABBR}"),
	(f"Actividades - Ritmos Latinos - {COMPANY_ABBR}", f"Ritmos Latinos - {COMPANY_ABBR}"),
	(f"Actividades - Zumba - {COMPANY_ABBR}", f"Zumba - {COMPANY_ABBR}"),
	(f"Fitness - Gimnasio de Musculacion - {COMPANY_ABBR}", f"Gimnasio de Musculacion - {COMPANY_ABBR}"),
	(f"Gastronomía - Buffet - {COMPANY_ABBR}", f"Buffet - {COMPANY_ABBR}"),
	(f"Gastronomía - Peña de Rock - {COMPANY_ABBR}", f"Peña de Rock - {COMPANY_ABBR}"),
	(f"Gastronomía - Restaurante - {COMPANY_ABBR}", f"Restaurante - {COMPANY_ABBR}"),
	(f"Alquileres - Temporal - {COMPANY_ABBR}", f"Temporal - {COMPANY_ABBR}"),
	(f"Alquileres - Recurrente - {COMPANY_ABBR}", f"Recurrente - {COMPANY_ABBR}"),
)


def _company_root_cost_center(company: str) -> str:
	root = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "name": ["like", f"% - {COMPANY_ABBR}"]},
		"name",
		order_by="lft asc",
	)
	# Prefer the true NestedSet root (no parent).
	for name in frappe.get_all(
		"Cost Center",
		filters={"company": company, "is_group": 1},
		pluck="name",
		order_by="lft asc",
	):
		parent = frappe.db.get_value("Cost Center", name, "parent_cost_center")
		if not parent:
			return name
	candidate = f"{company} - {COMPANY_ABBR}"
	if frappe.db.exists("Cost Center", candidate):
		return candidate
	if root:
		return root
	frappe.throw(f"No encuentro Cost Center raíz para company={company!r}")


def reparent_main_children_to_company_root() -> list[str]:
	"""Mueve hijos directos de Main a la raíz de la Company."""
	if not frappe.db.exists("Cost Center", MAIN_CC):
		return []

	company = resolve_icdpe_company()
	root = _company_root_cost_center(company)
	moved: list[str] = []
	for name in frappe.get_all(
		"Cost Center",
		filters={"parent_cost_center": MAIN_CC, "company": company},
		pluck="name",
	):
		doc = frappe.get_doc("Cost Center", name)
		if doc.parent_cost_center == root:
			continue
		doc.parent_cost_center = root
		doc.save(ignore_permissions=True)
		moved.append(name)
	return moved


def rename_leaf_cost_centers() -> dict[str, str]:
	"""Renombra hojas según COST_CENTER_RENAME_MAP. Devuelve old→new aplicados."""
	applied: dict[str, str] = {}
	for old, new in COST_CENTER_RENAME_MAP:
		if not frappe.db.exists("Cost Center", old):
			continue
		if old == new:
			continue
		if frappe.db.exists("Cost Center", new):
			# Destino ya existe (idempotente o parcial): no fusionar aquí.
			continue
		frappe.rename_doc("Cost Center", old, new, force=True, merge=False)
		applied[old] = new
	return applied


def disable_empty_main() -> bool:
	"""Deshabilita Main si existe y no tiene hijos."""
	if not frappe.db.exists("Cost Center", MAIN_CC):
		return False
	n_children = frappe.db.count("Cost Center", {"parent_cost_center": MAIN_CC})
	if n_children:
		return False
	if frappe.db.get_value("Cost Center", MAIN_CC, "disabled"):
		return False
	frappe.db.set_value("Cost Center", MAIN_CC, "disabled", 1, update_modified=True)
	return True


ADMIN_CC = f"Administración - {COMPANY_ABBR}"
CUOTAS_CC = f"Cuotas Sociales - {COMPANY_ABBR}"
FITNESS_CC = f"Fitness - {COMPANY_ABBR}"
ACTIVIDADES_CC = f"Actividades - {COMPANY_ABBR}"

# Hojas de fitness que deben colgar de Fitness (no de Actividades).
FITNESS_LEAF_CCS: tuple[str, ...] = (
	f"CrossFit - {COMPANY_ABBR}",
	f"Funcional - {COMPANY_ABBR}",
	f"Gimnasio de Musculacion - {COMPANY_ABBR}",
)


def reparent_fitness_leaves() -> list[str]:
	"""Mueve CrossFit / Funcional (y gym si hace falta) bajo Fitness."""
	if not frappe.db.exists("Cost Center", FITNESS_CC):
		return []
	moved: list[str] = []
	for name in FITNESS_LEAF_CCS:
		if not frappe.db.exists("Cost Center", name):
			continue
		doc = frappe.get_doc("Cost Center", name)
		if doc.parent_cost_center == FITNESS_CC:
			continue
		doc.parent_cost_center = FITNESS_CC
		doc.save(ignore_permissions=True)
		moved.append(name)
	return moved


def _ensure_parking_group(company: str, root: str) -> str:
	"""Usa Main (o crea parking temporal) para reordenar hermanos bajo la raíz."""
	if frappe.db.exists("Cost Center", MAIN_CC):
		# Reactivar temporalmente como grupo para estacionar nodos.
		frappe.db.set_value("Cost Center", MAIN_CC, "disabled", 0, update_modified=False)
		frappe.db.set_value("Cost Center", MAIN_CC, "is_group", 1, update_modified=False)
		return MAIN_CC

	parking_name = f"_ICDPE reorder parking - {COMPANY_ABBR}"
	if not frappe.db.exists("Cost Center", parking_name):
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": "_ICDPE reorder parking",
				"parent_cost_center": root,
				"company": company,
				"is_group": 1,
			}
		).insert(ignore_permissions=True)
	return parking_name


def reorder_root_institution_leaves_first() -> list[str]:
	"""Deja Administración y Cuotas Sociales como primeros hijos de la raíz contable."""
	company = resolve_icdpe_company()
	root = _company_root_cost_center(company)
	priority = [c for c in (ADMIN_CC, CUOTAS_CC) if frappe.db.exists("Cost Center", c)]
	if not priority:
		return []

	siblings = frappe.get_all(
		"Cost Center",
		filters={"parent_cost_center": root, "company": company},
		pluck="name",
		order_by="lft asc",
	)
	# Conservar el resto (grupos de área); excluir Main/parking del orden final.
	rest = [
		n
		for n in siblings
		if n not in priority and n != MAIN_CC and not n.startswith("_ICDPE reorder parking")
	]
	desired = priority + rest

	# ¿Ya está en el orden pedido?
	if siblings[: len(priority)] == priority:
		return []

	parking = _ensure_parking_group(company, root)
	for name in desired:
		doc = frappe.get_doc("Cost Center", name)
		if doc.parent_cost_center != parking:
			doc.parent_cost_center = parking
			doc.save(ignore_permissions=True)

	for name in desired:
		doc = frappe.get_doc("Cost Center", name)
		doc.parent_cost_center = root
		doc.save(ignore_permissions=True)

	disable_empty_main()
	# Limpiar parking temporal si no es Main
	if parking != MAIN_CC and frappe.db.exists("Cost Center", parking):
		if frappe.db.count("Cost Center", {"parent_cost_center": parking}) == 0:
			frappe.delete_doc("Cost Center", parking, force=1, ignore_permissions=True)

	return desired


def run_flatten_rename_icdpe_cost_centers() -> dict[str, Any]:
	"""Pipeline idempotente: reparent Main → rename → fitness → orden raíz → disable Main."""
	resolve_icdpe_company()
	moved = reparent_main_children_to_company_root()
	renamed = rename_leaf_cost_centers()
	fitness_moved = reparent_fitness_leaves()
	root_order = reorder_root_institution_leaves_first()
	main_disabled = disable_empty_main()
	return {
		"moved_from_main": moved,
		"renamed": renamed,
		"fitness_moved": fitness_moved,
		"root_order": root_order,
		"main_disabled": main_disabled,
	}
