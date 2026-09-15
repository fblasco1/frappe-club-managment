"""Renombra informe «Deuda del club por actividad» → «Deuda por actividad»."""

from __future__ import annotations

import frappe

OLD_REPORT = "Deuda del club por actividad"
NEW_REPORT = "Deuda por actividad"
NEW_LABEL = "Deuda por actividad"


def execute() -> None:
	if frappe.db.exists("Report", OLD_REPORT):
		if frappe.db.exists("Report", NEW_REPORT):
			frappe.delete_doc("Report", OLD_REPORT, force=1)
		else:
			frappe.rename_doc("Report", OLD_REPORT, NEW_REPORT, force=True)

	for doctype in ("Workspace Link", "Workspace Sidebar Item"):
		for row in frappe.get_all(
			doctype,
			filters={"link_type": "Report", "link_to": OLD_REPORT},
			fields=["name"],
		):
			frappe.db.set_value(
				doctype,
				row.name,
				{"link_to": NEW_REPORT, "label": NEW_LABEL},
				update_modified=False,
			)

	for row in frappe.get_all(
		"Workspace Link",
		filters={"link_type": "DocType", "link_to": "Club Settings", "label": "Configuración del club"},
		pluck="name",
	):
		frappe.db.set_value("Workspace Link", row, "label", "Configuración", update_modified=False)

	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Report")
