"""One-off ops: inspect Item create permission + duplicates. Run via:

bench --site dev.localhost run-tests --module ...  (no)
Better: bench --site dev.localhost execute club_management.scripts.ops_inspect_items.run
"""

from __future__ import annotations

from collections import defaultdict

import frappe


def run() -> None:
	frappe.set_user("Administrator")
	print("HAS_CREATE", frappe.has_permission("Item", "create"))
	print("HAS_WRITE", frappe.has_permission("Item", "write"))
	print("ITEM_NAMING", frappe.db.get_single_value("Stock Settings", "item_naming_by"))
	print("DEFAULT_UOM", frappe.db.get_single_value("Stock Settings", "stock_uom"))

	group = (
		frappe.db.get_value("Item Group", {"name": "Services"}, "name")
		or frappe.db.get_value("Item Group", {"is_group": 0}, "name")
		or "All Item Groups"
	)
	uom = frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"
	print("PICK_GROUP", group, "UOM", uom)

	code = "RECARGO-MORA"
	if frappe.db.exists("Item", code):
		print("EXISTS", code)
	else:
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": "Recargo por mora",
					"item_group": group,
					"stock_uom": uom,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"is_purchase_item": 0,
					"standard_rate": 0,
				}
			)
			doc.insert(ignore_permissions=True)
			frappe.db.commit()
			print("CREATED", code)
		except Exception as exc:  # noqa: BLE001
			frappe.db.rollback()
			print("CREATE_ERROR", type(exc).__name__, str(exc)[:800])

	# Without ignore_permissions
	code2 = "RECARGO-MORA-PERM-TEST"
	if frappe.db.exists("Item", code2):
		frappe.delete_doc("Item", code2, force=True, ignore_permissions=True)
		frappe.db.commit()
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code2,
				"item_name": "Recargo mora perm test",
				"item_group": group,
				"stock_uom": uom,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 0,
			}
		)
		doc.insert()  # respect permissions
		frappe.db.commit()
		print("CREATE_WITH_PERMS_OK", code2)
		frappe.delete_doc("Item", code2, force=True, ignore_permissions=True)
		frappe.db.commit()
	except Exception as exc:  # noqa: BLE001
		frappe.db.rollback()
		print("CREATE_WITH_PERMS_ERROR", type(exc).__name__, str(exc)[:800])

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
		],
		order_by="item_name, name",
		limit_page_length=1000,
	)
	print("ITEM_COUNT", len(rows))
	by_name: dict[str, list[str]] = defaultdict(list)
	for row in rows:
		key = (row.item_name or "").strip().lower()
		by_name[key].append(row.name)
	dups = {k: v for k, v in by_name.items() if len(v) > 1 and k}
	print("DUP_GROUPS", len(dups))
	for key, names in sorted(dups.items(), key=lambda x: -len(x[1]))[:40]:
		print("DUP", len(names), key, "=>", " ; ".join(names))

	for row in rows:
		blob = f"{row.name} {row.item_name or ''}".lower()
		if any(tok in blob for tok in ("cuota", "mora", "recargo", "arancel", "social", "basquet", "fútbol", "futbol", "cargo")):
			print(
				"CLUB",
				row.name,
				"|",
				row.item_name,
				"|",
				row.item_group,
				"|",
				f"dis={row.disabled}",
				f"sales={row.is_sales_item}",
				f"stock={row.is_stock_item}",
				f"rate={row.standard_rate}",
			)

	# DocPerm on Item for roles
	perms = frappe.get_all(
		"DocPerm",
		filters={"parent": "Item"},
		fields=["role", "permlevel", "read", "write", "create", "delete"],
		order_by="role",
	)
	print("ITEMPERMS", len(perms))
	for perm in perms:
		if int(perm.create or 0) or perm.role in ("System Manager", "Item Manager", "Stock User", "All"):
			print(
				"PERM",
				perm.role,
				f"c={perm.create}",
				f"w={perm.write}",
				f"r={perm.read}",
				f"d={perm.delete}",
				f"lvl={perm.permlevel}",
			)


def fix_item_create_perm() -> None:
	"""Ensure System Manager can create Item (Producto) from Desk list."""
	import frappe

	frappe.set_user("Administrator")
	from frappe.core.page.permission_manager.permission_manager import add_permission, update_permission_property

	# Show current
	user = frappe.get_doc("User", "Administrator")
	print("Admin roles", [r.role for r in user.roles])
	print("has_permission create", frappe.has_permission("Item", ptype="create", user="Administrator"))

	# Add System Manager create if missing via Custom DocPerm / Role Permission
	existing = frappe.get_all(
		"DocPerm",
		filters={"parent": "Item", "role": "System Manager"},
		fields=["name", "create", "write", "read", "delete"],
	)
	custom = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": "Item", "role": "System Manager"},
		fields=["name", "create", "write", "read", "delete"],
	)
	print("DocPerm SM", existing)
	print("Custom DocPerm SM", custom)

	# Also check Item Manager on Administrator
	roles = frappe.get_roles("Administrator")
	if "Item Manager" not in roles:
		user.append("roles", {"role": "Item Manager"})
		user.save(ignore_permissions=True)
		print("ADDED Item Manager to Administrator")
	else:
		print("Admin already has Item Manager")

	# Ensure Item Manager has create (standard)
	im = frappe.get_all(
		"DocPerm",
		filters={"parent": "Item", "role": "Item Manager", "permlevel": 0},
		fields=["name", "create", "write", "read"],
	)
	print("Item Manager perms", im)

	# Clear cache so Desk sees New button
	frappe.clear_cache()
	frappe.db.commit()

	# Verify RECARGO-MORA for user
	print("RECARGO-MORA", frappe.db.exists("Item", "RECARGO-MORA"))
	settings = frappe.get_single("Club Settings")
	if not settings.item_recargo_mora:
		settings.item_recargo_mora = "RECARGO-MORA"
		settings.save(ignore_permissions=True)
		frappe.db.commit()
	print("item_recargo_mora", settings.item_recargo_mora)
	print("DONE: logout/login or Ctrl+Shift+R; buscar RECARGO-MORA en Producto")
