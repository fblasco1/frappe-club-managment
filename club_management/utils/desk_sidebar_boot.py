"""Utilidades compartidas para ítems de sidebar Desk en bootinfo."""

from __future__ import annotations

from typing import Any

import frappe


def enrich_sidebar_link_item(item: dict[str, Any]) -> dict[str, Any]:
	"""Añade metadatos de Report necesarios para rutas del sidebar Frappe."""
	link_to = item.get("link_to")
	link_type = item.get("link_type")
	if link_type == "Report" and link_to and frappe.db.exists("Report", link_to):
		report_type, ref_doctype = frappe.db.get_value(
			"Report", link_to, ["report_type", "ref_doctype"]
		)
		item["report"] = {
			"report_type": report_type,
			"ref_doctype": ref_doctype,
		}
	return item
