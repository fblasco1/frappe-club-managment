"""Reemplaza «Deuda por actividad» y «Deuda cuotas sociales» por «Deuda de socios» en menús Desk."""

from __future__ import annotations

import frappe

from club_management.activities.setup.actividades_workspace_sidebar import (
	sync_actividades_workspace_sidebar,
)
from club_management.members.setup.secretaria_workspace_sidebar import (
	sync_secretaria_workspace_sidebar,
)

NEW_REPORT = "Deuda de socios"
RETIRED = ("Deuda por actividad", "Deuda cuotas sociales")


def _retarget_links() -> None:
	for doctype in ("Workspace Link", "Workspace Sidebar Item"):
		con_nuevo = set(
			frappe.get_all(doctype, filters={"link_type": "Report", "link_to": NEW_REPORT}, pluck="parent")
		)
		rows = frappe.get_all(
			doctype,
			filters={"link_type": "Report", "link_to": ["in", list(RETIRED)]},
			fields=["name", "parent"],
			order_by="idx asc",
		)
		for row in rows:
			if row.parent in con_nuevo:
				frappe.delete_doc(doctype, row.name, ignore_permissions=True, force=True)
				continue
			frappe.db.set_value(
				doctype, row.name, {"link_to": NEW_REPORT, "label": NEW_REPORT}, update_modified=False
			)
			con_nuevo.add(row.parent)


def execute() -> None:
	if not frappe.db.exists("Report", NEW_REPORT):
		return
	_retarget_links()
	sync_secretaria_workspace_sidebar()
	sync_actividades_workspace_sidebar()
	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Workspace Sidebar")
	frappe.clear_cache(doctype="Report")
