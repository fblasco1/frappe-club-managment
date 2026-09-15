"""Ops: usage of duplicate Items + wire RECARGO-MORA in Club Settings."""

from __future__ import annotations

import frappe


def _usage(code: str) -> dict[str, int]:
	refs: dict[str, int] = {
		"sales_invoice_item": frappe.db.count("Sales Invoice Item", {"item_code": code}),
	}
	candidates = (
		("Actividad", "item_arancel"),
		("Actividad", "item"),
		("Cargo Extra", "item"),
		("Cargo Extra Concepto", "item"),
		("Cargo Socio", "item"),
		("Grupo Actividad", "item_arancel"),
	)
	for doctype, field in candidates:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.get_meta(doctype).has_field(field):
			continue
		refs[f"{doctype}.{field}"] = frappe.db.count(doctype, {field: code})
	return refs


def run() -> None:
	frappe.set_user("Administrator")

	# Ensure mora item + Club Settings
	if not frappe.db.exists("Item", "RECARGO-MORA"):
		group = frappe.db.get_value("Item Group", {"name": "Services"}, "name") or frappe.db.get_value(
			"Item Group", {"is_group": 0}, "name"
		)
		uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "RECARGO-MORA",
				"item_name": "Recargo por mora",
				"item_group": group,
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 0,
			}
		).insert(ignore_permissions=True)

	settings = frappe.get_single("Club Settings")
	if settings.item_recargo_mora != "RECARGO-MORA":
		settings.item_recargo_mora = "RECARGO-MORA"
		settings.save(ignore_permissions=True)
		frappe.db.commit()
		print("SET item_recargo_mora=RECARGO-MORA")
	else:
		print("OK item_recargo_mora already RECARGO-MORA")

	pairs = [
		("ICDPE-DANZA", "ICDPE-ARANCEL-MENSUAL-DANZA-GENERAL"),
		("ICDPE-RITMOS-LATINOS", "ICDPE-ARANCEL-MENSUAL-RITMOS_LATINOS-GENERAL"),
		("ICDPE-SHUI-LU", "ICDPE-ARANCEL-MENSUAL-SHUI_LU-GENERAL"),
		("ICDPE-TAEKWONDO", "ICDPE-ARANCEL-MENSUAL-TAEKWONDO-GENERAL"),
		("ICDPE-FIN-INDUMENTARIA", "ICDPE-VENTA-INDUMENTARIA"),
	]
	print("=== Exact name duplicates ===")
	for left, right in pairs:
		print(left, _usage(left))
		print(right, _usage(right))
		print("---")

	print("=== Cuota / mora items ===")
	for code in (
		"ICDPE-CUOTA-SOCIAL",
		"CLUB-Cuota-Social-Base",
		"Cuota Social ADHERENTE",
		"Cuota Social MENOR",
		"Cuota Social 2° hermano",
		"RECARGO-MORA",
	):
		if frappe.db.exists("Item", code):
			print(code, _usage(code))

	print("item_cuota_social", settings.item_cuota_social)
	print("item_recargo_mora", settings.item_recargo_mora)
	for row in settings.cuotas_categoria or []:
		print("cuota_cat", row.categoria, getattr(row, "item", None), row.monto)

	# Near-duplicate catalogs: short ICDPE-* vs ICDPE-ARANCEL-MENSUAL-*
	shorts = frappe.get_all(
		"Item",
		filters={"name": ["like", "ICDPE-%"], "disabled": 0},
		fields=["name", "item_name", "item_group", "standard_rate"],
		limit_page_length=500,
	)
	arancel_mensual = [r for r in shorts if r.name.startswith("ICDPE-ARANCEL-MENSUAL-")]
	canon = [r for r in shorts if not r.name.startswith("ICDPE-ARANCEL-MENSUAL-") and "ARANCEL" not in r.name]
	print("COUNT ICDPE-ARANCEL-MENSUAL-*", len(arancel_mensual))
	print("COUNT other ICDPE-*", len(canon))

	# Disable unused exact duplicates (right side if unused and left has usage or vice versa)
	disabled = []
	for left, right in pairs:
		u_l, u_r = _usage(left), _usage(right)
		sum_l = sum(u_l.values())
		sum_r = sum(u_r.values())
		# Prefer shorter / canonical ICDPE-* without ARANCEL-MENSUAL
		keep, drop = left, right
		if sum_l == 0 and sum_r > 0:
			keep, drop = right, left
		elif sum_r == 0 and sum_l >= 0:
			keep, drop = left, right
		else:
			# both used or both unused: keep left (shorter), only disable right if unused
			if sum_r == 0 and drop == right:
				pass
			else:
				print("SKIP_BOTH_USED_OR_AMBIGUOUS", left, sum_l, right, sum_r)
				continue
		if sum(u_r.values() if drop == right else u_l.values()) == 0:
			doc = frappe.get_doc("Item", drop)
			if not int(doc.disabled or 0):
				doc.disabled = 1
				doc.save(ignore_permissions=True)
				disabled.append(drop)
				print("DISABLED", drop, "keep", keep)
	if disabled:
		frappe.db.commit()
	print("DISABLED_COUNT", len(disabled))


def disable_unused_catalog() -> None:
	"""Disable unused parallel catalog items (safe: only if zero SI/actividad/cargo refs)."""
	frappe.set_user("Administrator")
	disabled: list[str] = []

	# Unused legacy cuota item names (canonical is ICDPE-CUOTA-SOCIAL)
	for code in (
		"CLUB-Cuota-Social-Base",
		"Cuota Social ADHERENTE",
		"Cuota Social MENOR",
		"Cuota Social 2° hermano",
	):
		if not frappe.db.exists("Item", code):
			continue
		if sum(_usage(code).values()) > 0:
			print("KEEP_USED", code, _usage(code))
			continue
		doc = frappe.get_doc("Item", code)
		if not int(doc.disabled or 0):
			doc.disabled = 1
			doc.save(ignore_permissions=True)
			disabled.append(code)
			print("DISABLED", code)

	# Parallel import: ICDPE-ARANCEL-MENSUAL-* with no usage
	rows = frappe.get_all(
		"Item",
		filters={"name": ["like", "ICDPE-ARANCEL-MENSUAL-%"], "disabled": 0},
		pluck="name",
		limit_page_length=500,
	)
	for code in rows:
		if sum(_usage(code).values()) > 0:
			print("KEEP_USED", code, _usage(code))
			continue
		doc = frappe.get_doc("Item", code)
		doc.disabled = 1
		doc.save(ignore_permissions=True)
		disabled.append(code)
		print("DISABLED", code)

	# Move RECARGO-MORA to ICDPE cargos group if exists
	group = (
		frappe.db.get_value("Item Group", {"name": "ICDPE / Cargos varios"}, "name")
		or frappe.db.get_value("Item Group", {"name": ["like", "ICDPE / Cargo%"]}, "name")
	)
	if group and frappe.db.exists("Item", "RECARGO-MORA"):
		doc = frappe.get_doc("Item", "RECARGO-MORA")
		if doc.item_group != group:
			doc.item_group = group
			doc.save(ignore_permissions=True)
			print("MOVED RECARGO-MORA ->", group)

	if disabled:
		frappe.db.commit()
	print("DISABLED_TOTAL", len(disabled))
