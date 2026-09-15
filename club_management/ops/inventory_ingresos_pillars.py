"""Inventario de Items en pilares de ingreso (ops one-shot)."""

from __future__ import annotations

from collections import defaultdict

import frappe

INGRESO_PILLARS = (
	"Ingresos de Socios y Membresías",
	"Ingresos por Actividades Deportivas",
	"Ingresos Comerciales y Alquileres",
	"Ingresos Institucionales",
)


def run() -> dict:
	by_pillar: dict[str, list[dict]] = {}
	for pillar in INGRESO_PILLARS:
		exists = bool(frappe.db.exists("Item Group", pillar))
		is_group = frappe.db.get_value("Item Group", pillar, "is_group") if exists else None
		parent = frappe.db.get_value("Item Group", pillar, "parent_item_group") if exists else None
		kids = (
			frappe.get_all("Item Group", filters={"parent_item_group": pillar}, pluck="name")
			if exists
			else []
		)
		items = []
		if exists:
			rows = frappe.get_all(
				"Item",
				filters={"item_group": pillar, "disabled": 0},
				fields=["name", "item_name", "standard_rate", "is_sales_item", "is_purchase_item"],
				order_by="name",
			)
			for r in rows:
				items.append(
					{
						"code": r.name,
						"name": r.item_name,
						"rate": float(r.standard_rate or 0),
						"sales": int(r.is_sales_item or 0),
					}
				)
		by_pillar[pillar] = {
			"exists": exists,
			"is_group": is_group,
			"parent": parent,
			"children": kids,
			"items": items,
		}
		print(f"\n## {pillar}")
		print(f"  exists={exists} is_group={is_group} parent={parent} children={kids}")
		print(f"  items_hab={len(items)}")
		for it in items:
			print(f"  - {it['code']} | {it['name']} | rate={it['rate']}")

	# egreso sample
	print("\n## EGRESO sample (pilares)")
	for p in (
		"Gastos de Estructura y Servicios",
		"Gastos de Personal (Nómina)",
		"Costos Operativos Deportivos",
		"Mantenimiento e Infraestructura",
	):
		if not frappe.db.exists("Item Group", p):
			print(f"  {p}: MISSING")
			continue
		isg = frappe.db.get_value("Item Group", p, "is_group")
		kids = frappe.get_all("Item Group", filters={"parent_item_group": p}, pluck="name")
		direct = frappe.db.count("Item", {"item_group": p, "disabled": 0})
		print(f"  {p}: is_group={isg} direct_items={direct} children={kids}")

	return {"pillars": {k: {"n": len(v["items"]), "is_group": v["is_group"]} for k, v in by_pillar.items()}}
