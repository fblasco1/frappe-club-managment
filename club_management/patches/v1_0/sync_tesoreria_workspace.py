"""Patch: sincroniza workspace Tesorería."""

from __future__ import annotations

import json
from pathlib import Path

import frappe

from club_management.patches.v1_0.ensure_finance_module import execute as ensure_module

WORKSPACE_NAME = "Tesorería"


def execute() -> None:
	ensure_module()
	path = (
		Path(frappe.get_app_path("club_management"))
		/ "finance"
		/ "workspace"
		/ "tesoreria"
		/ "tesoreria.json"
	)
	if not path.exists():
		return
	data = json.loads(path.read_text(encoding="utf-8"))
	for key in ("modified", "creation", "modified_by", "owner", "idx"):
		data.pop(key, None)

	name = data.get("name") or WORKSPACE_NAME
	if frappe.db.exists("Workspace", name):
		frappe.delete_doc("Workspace", name, force=1, ignore_permissions=True)

	# Normalizar links hijos
	links = []
	for link in data.get("links") or []:
		row = dict(link)
		row.setdefault("type", "Link")
		links.append(row)
	data["links"] = links

	shortcuts = []
	for sc in data.get("shortcuts") or []:
		row = dict(sc)
		row.setdefault("type", "Report")
		shortcuts.append(row)
	data["shortcuts"] = shortcuts

	frappe.get_doc(data).insert(ignore_permissions=True)
