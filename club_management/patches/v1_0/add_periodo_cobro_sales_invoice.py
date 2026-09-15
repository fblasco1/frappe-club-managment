"""Campo `periodo_cobro` en Sales Invoice para idempotencia de deuda mensual."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	name = "Sales Invoice-periodo_cobro"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"name": name,
			"dt": "Sales Invoice",
			"fieldname": "periodo_cobro",
			"label": "Período de cobro",
			"fieldtype": "Data",
			"insert_after": "socio",
			"read_only": 1,
			"no_copy": 1,
		}
	).insert(ignore_permissions=True)
