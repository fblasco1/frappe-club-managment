"""Workspace Secretaría: operación interna sin solicitudes ni grupo familiar."""

from __future__ import annotations

import json

import frappe

WORKSPACE_NAME = "Secretaría"

CONTENT: list[dict] = []

NUMBER_CARDS: list[dict] = []

LINKS = [
	{"label": "Socios", "link_to": "Socio", "link_type": "DocType", "type": "Link"},
	{
		"label": "Inscripciones a actividades",
		"link_to": "Inscripcion Actividad",
		"link_type": "DocType",
		"type": "Link",
	},
	{"label": "Actividades", "link_to": "Actividad", "link_type": "DocType", "type": "Link"},
	{
		"label": "Configuración del club",
		"link_to": "Club Settings",
		"link_type": "DocType",
		"type": "Link",
	},
]

SHORTCUTS = [
	{
		"color": "Blue",
		"doc_view": "List",
		"format": "{} Pend. pago",
		"label": "Socios pendientes de pago",
		"link_to": "Socio",
		"stats_filter": '{"estado": "Pendiente de Pago"}',
		"type": "DocType",
	},
	{
		"color": "Red",
		"doc_view": "List",
		"format": "{} Morosos",
		"label": "Socios morosos",
		"link_to": "Socio",
		"stats_filter": '{"estado": "Moroso"}',
		"type": "DocType",
	},
]

def _replace_child_table(parent: str, child_doctype: str, fieldname: str, rows: list[dict]) -> None:
	frappe.db.delete(child_doctype, {"parent": parent, "parenttype": "Workspace"})
	for idx, row in enumerate(rows, start=1):
		doc = frappe.get_doc(
			{
				"doctype": child_doctype,
				"parent": parent,
				"parenttype": "Workspace",
				"parentfield": fieldname,
				"idx": idx,
				**row,
			}
		)
		doc.insert(ignore_permissions=True)


def execute() -> None:
	if not frappe.db.exists("Workspace", WORKSPACE_NAME):
		return

	frappe.db.set_value(
		"Workspace",
		WORKSPACE_NAME,
		"content",
		json.dumps(CONTENT, ensure_ascii=False),
		update_modified=False,
	)
	_replace_child_table(WORKSPACE_NAME, "Workspace Link", "links", LINKS)
	_replace_child_table(WORKSPACE_NAME, "Workspace Shortcut", "shortcuts", SHORTCUTS)
	_replace_child_table(WORKSPACE_NAME, "Workspace Number Card", "number_cards", NUMBER_CARDS)
	frappe.clear_cache(doctype="Workspace")
