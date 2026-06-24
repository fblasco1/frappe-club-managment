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

INSCRIPCION_DOCTYPE = "Inscripcion Actividad"

# Grupos de ítems "generales" (no atados a una actividad puntual).
GRUPOS_CONCEPTOS_GENERALES: tuple[str, ...] = (
	"ICDPE / Cargos varios",
	"ICDPE / Actividades puntuales",
)

# Códigos de ítems generales conocidos que deben ofrecerse si existen.
CODIGOS_CONCEPTOS_GENERALES: tuple[str, ...] = (
	"ICDPE-MULTA",
	"ICDPE-CARGO-VARIOS",
	"ICDPE-COLONIAS",
	"ICDPE-EVENTOS",
	"ICDPE-VENTA-INDUMENTARIA",
)


def _selling_cost_center(item_code: str) -> str | None:
	"""Centro de costo de venta del ítem (de su `Item Default`)."""
	if not item_code:
		return None
	return frappe.db.get_value(
		"Item Default",
		{"parent": item_code, "selling_cost_center": ["is", "set"]},
		"selling_cost_center",
	)


def _item_cobrable(item_code: str) -> bool:
	data = frappe.db.get_value(
		"Item", item_code, ["is_stock_item", "disabled"], as_dict=True
	)
	if not data:
		return False
	return not data.is_stock_item and not data.disabled


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
	rows = frappe.get_all(
		"Item Default",
		filters={"selling_cost_center": ["in", list(cost_centers)]},
		fields=["parent"],
	)
	codes: list[str] = []
	seen: set[str] = set()
	for row in rows:
		code = row.parent
		if code in seen or code in excluir:
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
			if code not in seen:
				seen.add(code)
				codes.append(code)
	for code in CODIGOS_CONCEPTOS_GENERALES:
		if code in seen:
			continue
		if frappe.db.exists("Item", code) and _item_cobrable(code):
			seen.add(code)
			codes.append(code)
	return codes


def item_codes_cargo_extra_socio(socio_name: str) -> list[str]:
	"""Códigos de ítems ofrecibles como cargo extra para el socio."""
	cost_centers, aranceles = _cost_centers_y_aranceles_socio(socio_name)
	por_actividad = _items_de_cost_centers(cost_centers, excluir=aranceles)
	generales = _conceptos_generales()

	out: list[str] = []
	seen: set[str] = set()
	for code in por_actividad + generales:
		if code not in seen:
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
