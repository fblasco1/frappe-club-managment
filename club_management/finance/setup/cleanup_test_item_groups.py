"""Elimina Item Groups / Items de fixtures ERPNext (`_Test Item Group*`).

Spec: ``cleanup_test_item_groups.md``.
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.finance.setup.icdpe_finance_items import DEFAULT_ITEM_GROUP_ROOT

TEST_ITEM_GROUP_PREFIX = "_Test Item Group"


def _fallback_item_group() -> str:
	for candidate in ("Products", "All Item Groups"):
		if frappe.db.exists("Item Group", candidate):
			# Prefer a leaf for Items
			if candidate == DEFAULT_ITEM_GROUP_ROOT:
				continue
			if int(frappe.db.get_value("Item Group", candidate, "is_group") or 0) == 0:
				return candidate
	# Create a parking leaf if needed
	name = "ICDPE / Legacy test items"
	if not frappe.db.exists("Item Group", name):
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	return name


def _test_item_group_names() -> list[str]:
	return frappe.get_all(
		"Item Group",
		filters={"name": ["like", f"{TEST_ITEM_GROUP_PREFIX}%"]},
		pluck="name",
		order_by="lft desc",
	)


def purge_test_items_in_test_groups() -> dict[str, Any]:
	"""Borra ítems `_Test*` en esos grupos; reubica el resto a un grupo hoja."""
	groups = _test_item_group_names()
	deleted_items: list[str] = []
	moved_items: list[str] = []
	skipped: list[str] = []
	fallback = _fallback_item_group()

	for group in groups:
		for code in frappe.get_all("Item", filters={"item_group": group}, pluck="name"):
			if code.startswith("_Test") or code.startswith("Test "):
				try:
					frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
					deleted_items.append(code)
				except Exception as exc:
					skipped.append(f"{code}:{exc.__class__.__name__}")
			else:
				try:
					frappe.db.set_value("Item", code, "item_group", fallback, update_modified=False)
					moved_items.append(code)
				except Exception as exc:
					skipped.append(f"{code}:move:{exc.__class__.__name__}")
	return {"deleted_items": deleted_items, "moved_items": moved_items, "skipped": skipped}


def delete_test_item_groups() -> dict[str, Any]:
	"""Elimina grupos `_Test Item Group*` (hijos primero vía order_by lft desc)."""
	deleted: list[str] = []
	skipped: list[str] = []
	for name in _test_item_group_names():
		n_items = frappe.db.count("Item", {"item_group": name})
		n_children = frappe.db.count("Item Group", {"parent_item_group": name})
		if n_items or n_children:
			skipped.append(f"{name}:items={n_items}:children={n_children}")
			continue
		try:
			frappe.delete_doc("Item Group", name, force=1, ignore_permissions=True)
			deleted.append(name)
		except Exception as exc:
			skipped.append(f"{name}:{exc.__class__.__name__}")
	return {"deleted": deleted, "skipped": skipped}


def run_cleanup_test_item_groups() -> dict[str, Any]:
	items = purge_test_items_in_test_groups()
	# segunda pasada por si quedan hijos
	groups1 = delete_test_item_groups()
	groups2 = delete_test_item_groups()
	return {"items": items, "groups": {"pass1": groups1, "pass2": groups2}}
