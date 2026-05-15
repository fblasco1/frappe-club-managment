"""Listado de actividades disponibles en el formulario público de asociación."""

from __future__ import annotations

import frappe

# Fallback cuando el sitio aún no cargó ítems de actividades en ERPNext.
_ACTIVIDADES_DEFAULT: tuple[str, ...] = (
	"Fútbol",
	"Básquet",
	"Vóley",
	"Natación",
	"Gimnasio",
	"Tenis",
	"Handball",
	"Hockey",
)


def list_actividades_asociacion() -> list[dict[str, str]]:
	"""Devuelve actividades seleccionables en el portal (value = label)."""
	if frappe.db.table_exists("tabItem"):
		items = frappe.get_all(
			"Item",
			filters={"disabled": 0, "is_sales_item": 1},
			fields=["name", "item_name"],
			order_by="item_name asc",
			limit_page_length=0,
		)
		if items:
			return [
				{"value": row.item_name or row.name, "label": row.item_name or row.name}
				for row in items
			]

	return [{"value": label, "label": label} for label in _ACTIVIDADES_DEFAULT]
