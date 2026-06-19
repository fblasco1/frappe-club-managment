"""Workspace Secretaría: panel KPI custom sin widgets nativos."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "Secretaría"


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	frappe.db.set_value(
		"Workspace",
		WORKSPACE_NAME,
		"content",
		json.dumps([]),
		update_modified=False,
	)
	frappe.db.delete("Workspace Number Card", {"parent": WORKSPACE_NAME})
	frappe.clear_cache(doctype="Workspace")
