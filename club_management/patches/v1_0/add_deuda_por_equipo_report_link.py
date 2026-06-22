"""Agrega enlace al reporte Deuda por equipo en workspace Secretaría."""

from __future__ import annotations

import frappe

WORKSPACE_NAME = "Secretaría"
REPORT_NAME = "Deuda por equipo"


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return
	if not frappe.db.exists("Report", REPORT_NAME):
		return

	exists = frappe.db.exists(
		"Workspace Link",
		{
			"parent": WORKSPACE_NAME,
			"link_type": "Report",
			"link_to": REPORT_NAME,
		},
	)
	if exists:
		return

	doc = frappe.get_doc(
		{
			"doctype": "Workspace Link",
			"parent": WORKSPACE_NAME,
			"parenttype": "Workspace",
			"parentfield": "links",
			"label": "Deuda por equipo",
			"link_type": "Report",
			"link_to": REPORT_NAME,
			"type": "Link",
			"is_query_report": 1,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.clear_cache(doctype="Workspace")
