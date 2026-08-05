"""Snapshot of Item catalog after cleanup. Run: bench --site X execute club_management.ops.item_catalog_report.run"""

from __future__ import annotations

from collections import defaultdict

import frappe


def run() -> dict:
	frappe.set_user("Administrator")
	rows = frappe.get_all(
		"Item",
		fields=[
			"name",
			"item_name",
			"item_group",
			"disabled",
			"is_sales_item",
			"is_stock_item",
			"standard_rate",
			"stock_uom",
		],
		order_by="disabled asc, item_group asc, name asc",
		limit_page_length=2000,
	)

	by_group: dict[str, list] = defaultdict(list)
	enabled = disabled = 0
	for r in rows:
		if int(r.disabled or 0):
			disabled += 1
		else:
			enabled += 1
		by_group[r.item_group or "(sin grupo)"].append(r)

	settings = frappe.get_single("Club Settings")
	cuotas = []
	for row in settings.cuotas_categoria or []:
		cuotas.append(
			{
				"categoria": row.categoria,
				"item": getattr(row, "item", None),
				"monto": row.monto,
			}
		)

	# Exact name dups among enabled
	by_iname: dict[str, list[str]] = defaultdict(list)
	for r in rows:
		if int(r.disabled or 0):
			continue
		key = (r.item_name or "").strip().lower()
		if key:
			by_iname[key].append(r.name)
	dups = {k: v for k, v in by_iname.items() if len(v) > 1}

	report = {
		"total": len(rows),
		"enabled": enabled,
		"disabled": disabled,
		"item_cuota_social": settings.item_cuota_social,
		"item_recargo_mora": settings.item_recargo_mora,
		"cuotas_categoria": cuotas,
		"dup_item_name_enabled": dups,
		"groups": {
			g: {
				"enabled": sum(1 for x in items if not int(x.disabled or 0)),
				"disabled": sum(1 for x in items if int(x.disabled or 0)),
				"items": [
					{
						"name": x.name,
						"item_name": x.item_name,
						"disabled": int(x.disabled or 0),
						"rate": x.standard_rate,
						"sales": int(x.is_sales_item or 0),
						"stock": int(x.is_stock_item or 0),
						"uom": x.stock_uom,
					}
					for x in items
				],
			}
			for g, items in sorted(by_group.items())
		},
	}

	# Console-friendly dump
	print("=== RESUMEN ===")
	print(f"Total={report['total']} habilitados={enabled} deshabilitados={disabled}")
	print(f"Club Settings item_cuota_social={report['item_cuota_social']}")
	print(f"Club Settings item_recargo_mora={report['item_recargo_mora']}")
	print("Cuotas por categoría:")
	for c in cuotas:
		print(f"  - {c['categoria']}: item={c['item']} monto={c['monto']}")
	print(f"Duplicados por nombre (solo habilitados): {len(dups)}")
	for k, names in sorted(dups.items()):
		print(f"  DUP '{k}': {names}")

	print("\n=== POR GRUPO (habilitados primero) ===")
	for g, info in report["groups"].items():
		print(f"\n## {g}  (hab={info['enabled']} dis={info['disabled']})")
		for it in info["items"]:
			flag = "DIS" if it["disabled"] else "OK "
			print(
				f"  [{flag}] {it['name']} | {it['item_name']} | rate={it['rate']} | "
				f"sales={it['sales']} stock={it['stock']} uom={it['uom']}"
			)

	return report
