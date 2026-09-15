"""Centro de costo dedicado para la Cuota Social.

Los ingresos por cuota social se imputan a un centro de costo propio
(«Cuotas Sociales») en lugar de «Administración», para separar en el estado de
resultados el ingreso social del gasto de estructura.

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.
"""

from __future__ import annotations

import frappe

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import _default_company

COST_CENTER_LABEL = "Cuotas Sociales"


def _cost_center_name(company: str) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	return f"{COST_CENTER_LABEL} - {abbr}"


def _parent_cost_center(company: str) -> str | None:
	"""Grupo padre: el mismo de «Administración» si existe; si no, el raíz del árbol."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	admin = frappe.db.get_value(
		"Cost Center", f"Administración - {abbr}", "parent_cost_center"
	)
	if admin:
		return admin
	return frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name")


def _cuota_item_codes(company: str) -> set[str]:
	"""Ítems de cuota social usados por el club (settings + cuenta de ingreso + constante)."""
	codes: set[str] = {CUOTA_SOCIAL_ITEM_CODE}

	try:
		settings = frappe.get_single("Club Settings")
		for row in settings.get("cuotas_categoria") or []:
			if row.item:
				codes.add(row.item)
	except Exception:
		pass

	# Ítems cuyo `Item Default` apunta a la cuenta de ingreso «Cuota social».
	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": ["like", "%uota social%"]},
		"name",
	)
	if account:
		for item_code in frappe.get_all(
			"Item Default",
			filters={"company": company, "income_account": account},
			pluck="parent",
		):
			codes.add(item_code)

	return codes


def ensure_cuota_social_cost_center(company: str | None = None) -> str:
	"""Crea (si falta) el CC «Cuotas Sociales» y lo fija en los ítems de cuota social."""
	company = company or _default_company()
	name = _cost_center_name(company)

	if not frappe.db.exists("Cost Center", name):
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": COST_CENTER_LABEL,
				"company": company,
				"is_group": 0,
				"parent_cost_center": _parent_cost_center(company),
			}
		).insert(ignore_permissions=True)

	for item_code in _cuota_item_codes(company):
		_set_item_default_cost_center(item_code, company, name)
	return name


def _set_item_default_cost_center(item_code: str, company: str, cost_center: str) -> None:
	if not frappe.db.exists("Item", item_code):
		return
	item = frappe.get_doc("Item", item_code)
	row = next((d for d in (item.get("item_defaults") or []) if d.company == company), None)
	if row is None:
		item.append(
			"item_defaults",
			{"company": company, "selling_cost_center": cost_center},
		)
	elif row.selling_cost_center == cost_center:
		return
	else:
		row.selling_cost_center = cost_center
	item.save(ignore_permissions=True)
