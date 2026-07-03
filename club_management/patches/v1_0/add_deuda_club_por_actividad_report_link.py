"""Agrega enlace al reporte Deuda del club por actividad."""

from __future__ import annotations

import frappe

WORKSPACES = ("Secretaría", "Gestión de Actividades")
REPORT_NAME = "Deuda del club por actividad"


def execute() -> None:
	for workspace in WORKSPACES:
		if not frappe.db.exists("Workspace", workspace):
			continue
		if not frappe.db.exists("Report", REPORT_NAME):
			continue
		exists = frappe.db.exists(
			"Workspace Link",
			{
				"parent": workspace,
				"link_type": "Report",
				"link_to": REPORT_NAME,
			},
		)
		if exists:
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Link",
				"parent": workspace,
				"parenttype": "Workspace",
				"parentfield": "links",
				"label": "Deuda del club por actividad",
				"link_type": "Report",
				"link_to": REPORT_NAME,
				"type": "Link",
				"is_query_report": 1,
			}
		)
		doc.insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Workspace")
