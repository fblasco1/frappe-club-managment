"""Oculta workspaces ERPNext de Stock no usados por el club (servicios)."""

from __future__ import annotations

import frappe

STOCK_WORKSPACES: tuple[str, ...] = ("Stock",)


def hide_stock_workspaces() -> list[str]:
	hidden: list[str] = []
	for name in STOCK_WORKSPACES:
		if not frappe.db.exists("Workspace", name):
			continue
		frappe.db.set_value("Workspace", name, "is_hidden", 1, update_modified=False)
		hidden.append(name)
	if hidden:
		frappe.clear_cache(doctype="Workspace")
	return hidden
