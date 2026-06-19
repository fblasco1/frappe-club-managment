"""Campos custom ERPNext para vincular facturas y clientes al Socio."""

from __future__ import annotations

import frappe


def _upsert_custom_field(
	*,
	dt: str,
	fieldname: str,
	label: str,
	fieldtype: str = "Link",
	options: str = "Socio",
	insert_after: str = "customer",
) -> None:
	name = f"{dt}-{fieldname}"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"name": name,
			"dt": dt,
			"fieldname": fieldname,
			"label": label,
			"fieldtype": fieldtype,
			"options": options,
			"insert_after": insert_after,
		}
	).insert(ignore_permissions=True)


def execute() -> None:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	_upsert_custom_field(
		dt="Sales Invoice",
		fieldname="socio",
		label="Socio",
		insert_after="customer",
	)
	_upsert_custom_field(
		dt="Customer",
		fieldname="socio",
		label="Socio",
		insert_after="customer_name",
	)
