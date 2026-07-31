"""Conceptos cobrables sugeridos para cargos extra.

Spec: `cargo_extra_conceptos_y_facturacion.md`.

Regla: ofrecer los conceptos vinculados a las actividades en las que el socio
está inscripto (vía centro de costo compartido del arancel/cuota federativa)
más conceptos generales que no pertenecen a ninguna actividad (multa, etc.).
"""

from __future__ import annotations

import frappe

from club_management.activities.services.inscripcion_socio import (
	resolve_item_arancel_inscripcion,
)
from club_management.finance.setup.icdpe_income_item_groups import INGRESO_SOCIOS
from club_management.members.services.cobranza_manual import _default_company

INSCRIPCION_DOCTYPE = "Inscripcion Actividad"

# Grupos de ítems "generales" (no atados a una actividad puntual).
GRUPOS_CONCEPTOS_GENERALES: tuple[str, ...] = (INGRESO_SOCIOS,)

# Códigos de ítems generales conocidos que deben ofrecerse si existen.
CODIGOS_CONCEPTOS_GENERALES: tuple[str, ...] = (
	"ICDPE-MULTA",
	"ICDPE-CARGO-VARIOS",
	"ICDPE-COLONIAS",
	"ICDPE-EVENTOS",
	"ICDPE-VENTA-INDUMENTARIA",
)

# No ofrecer cuota social / inscripción como "cargo extra" genérico.
CODIGOS_EXCLUIR_CONCEPTOS_GENERALES: frozenset[str] = frozenset(
	{
		"ICDPE-CUOTA-SOCIAL",
		"ICDPE-INSCRIPCION",
	}
)


def _selling_cost_center(item_code: str) -> str | None:
	"""Centro de costo de venta del ítem (de su `Item Default` por empresa)."""
	if not item_code:
		return None
	try:
		company = _default_company()
	except Exception:
		company = frappe.db.get_value("Company", {}, "name")
	if not company:
		return frappe.db.get_value(
			"Item Default",
			{"parent": item_code, "selling_cost_center": ["is", "set"]},
			"selling_cost_center",
		)
	return frappe.db.get_value(
		"Item Default",
		{
			"parent": item_code,
			"company": company,
			"selling_cost_center": ["is", "set"],
		},
		"selling_cost_center",
	)


def _item_cobrable(item_code: str) -> bool:
	data = frappe.db.get_value(
		"Item", item_code, ["is_stock_item", "disabled"], as_dict=True
	)
	if not data:
		return False
	return not data.is_stock_item and not data.disabled


def _item_es_arancel_actividad(item_code: str) -> bool:
	"""True si el ítem es arancel mensual de Actividad / Grupo / Equipo."""
	if not item_code:
		return False
	for doctype in ("Actividad", "Grupo Actividad", "Equipo Actividad"):
		if frappe.db.exists(doctype, {"item": item_code}):
			return True
	return False


def _item_es_concepto_general(item_code: str) -> bool:
	if item_code in CODIGOS_EXCLUIR_CONCEPTOS_GENERALES:
		return False
	if item_code in CODIGOS_CONCEPTOS_GENERALES:
		return True
	group = frappe.db.get_value("Item", item_code, "item_group")
	return bool(group and group in GRUPOS_CONCEPTOS_GENERALES)


def _cost_centers_y_aranceles_socio(socio_name: str) -> tuple[set[str], set[str]]:
	"""(centros de costo de actividades inscriptas, ítems de arancel a excluir)."""
	cost_centers: set[str] = set()
	aranceles: set[str] = set()
	for ins in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa"},
		pluck="name",
	):
		item = resolve_item_arancel_inscripcion(ins)
		if not item:
			continue
		aranceles.add(item)
		cc = _selling_cost_center(item)
		if cc:
			cost_centers.add(cc)
	return cost_centers, aranceles


def _items_de_cost_centers(cost_centers: set[str], excluir: set[str]) -> list[str]:
	if not cost_centers:
		return []
	try:
		company = _default_company()
	except Exception:
		company = frappe.db.get_value("Company", {}, "name")
	filters: dict = {"selling_cost_center": ["in", list(cost_centers)]}
	if company:
		filters["company"] = company
	rows = frappe.get_all(
		"Item Default",
		filters=filters,
		fields=["parent"],
	)
	codes: list[str] = []
	seen: set[str] = set()
	for row in rows:
		code = row.parent
		if not code or code in seen or code in excluir or _item_es_arancel_actividad(code):
			continue
		item_cc = _selling_cost_center(code)
		if not item_cc or item_cc not in cost_centers:
			continue
		seen.add(code)
		if _item_cobrable(code):
			codes.append(code)
	return codes


def _conceptos_generales() -> list[str]:
	codes: list[str] = []
	seen: set[str] = set()
	grupos_existentes = [g for g in GRUPOS_CONCEPTOS_GENERALES if frappe.db.exists("Item Group", g)]
	if grupos_existentes:
		for code in frappe.get_all(
			"Item",
			filters={
				"item_group": ["in", grupos_existentes],
				"is_stock_item": 0,
				"disabled": 0,
			},
			pluck="name",
		):
			if code in seen or _item_es_arancel_actividad(code):
				continue
			if code in CODIGOS_EXCLUIR_CONCEPTOS_GENERALES:
				continue
			seen.add(code)
			codes.append(code)
	for code in CODIGOS_CONCEPTOS_GENERALES:
		if code in seen:
			continue
		if frappe.db.exists("Item", code) and _item_cobrable(code):
			seen.add(code)
			codes.append(code)
	return codes


def federativa_item_codes_inscripcion(inscripcion_name: str) -> list[str]:
	"""Ítems de cuota federativa vinculados al centro de costo del arancel de la inscripción."""
	item_arancel = resolve_item_arancel_inscripcion(inscripcion_name)
	if not item_arancel:
		return []
	cc = _selling_cost_center(item_arancel)
	if not cc:
		return []
	return _items_de_cost_centers({cc}, excluir={item_arancel})


def item_codes_cargo_extra_socio(socio_name: str) -> list[str]:
	"""Códigos de ítems ofrecibles como cargo extra para el socio."""
	_, aranceles = _cost_centers_y_aranceles_socio(socio_name)
	por_actividad: list[str] = []
	seen_actividad: set[str] = set()
	for ins in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": socio_name, "estado": "Activa"},
		pluck="name",
	):
		for code in federativa_item_codes_inscripcion(ins):
			if code in seen_actividad or code in aranceles or _item_es_arancel_actividad(code):
				continue
			seen_actividad.add(code)
			por_actividad.append(code)
	generales = _conceptos_generales()

	out: list[str] = []
	seen: set[str] = set()
	for code in por_actividad + generales:
		if (
			code in seen
			or code in aranceles
			or _item_es_arancel_actividad(code)
		):
			continue
		if code in por_actividad or _item_es_concepto_general(code):
			seen.add(code)
			out.append(code)
	return out


def conceptos_cargo_extra_socio(socio_name: str) -> list[dict[str, str]]:
	"""Conceptos con nombre legible para mostrar en Desk."""
	result: list[dict[str, str]] = []
	for code in item_codes_cargo_extra_socio(socio_name):
		result.append(
			{
				"item_code": code,
				"item_name": frappe.db.get_value("Item", code, "item_name") or code,
			}
		)
	return result
