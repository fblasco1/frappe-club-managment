"""Patch: asegura Module Def Spaces."""

from __future__ import annotations

import frappe

MODULE_NAME = "Spaces"
APP_NAME = "club_management"


def execute() -> None:
	if frappe.db.exists("Module Def", MODULE_NAME):
		return
	frappe.get_doc(
		{
			"doctype": "Module Def",
			"module_name": MODULE_NAME,
			"app_name": APP_NAME,
		}
	).insert(ignore_permissions=True)
