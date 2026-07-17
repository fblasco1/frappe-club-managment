"""Seed de Suppliers críticos y masters financieros ICDPE."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.finance.setup.icdpe_finance_items import run_finance_items_seed
from club_management.setup.icdpe_company import resolve_icdpe_company

# (supplier_name, supplier_group hint)
FINANCE_SUPPLIERS: tuple[tuple[str, str], ...] = (
	("ICDPE-Sueldos Personal", "Services"),
	("ICDPE-AFIP 931", "Government"),
	("ICDPE-ART", "Insurance"),
	("ICDPE-UTEDYC", "Services"),
	("ICDPE-Servicios Publicos", "Services"),
	("ICDPE-Federaciones", "Services"),
	("ICDPE-Seguridad Eventos", "Services"),
	("ICDPE-Mantenimiento", "Services"),
)


def _ensure_supplier_group(name: str) -> str:
	if frappe.db.exists("Supplier Group", name):
		return name
	# ERPNext suele traer All Supplier Groups
	parent = "All Supplier Groups"
	if not frappe.db.exists("Supplier Group", parent):
		parent = frappe.db.get_value("Supplier Group", {"is_group": 1}, "name") or name
	if name == parent:
		return name
	if not frappe.db.exists("Supplier Group", name):
		try:
			frappe.get_doc(
				{
					"doctype": "Supplier Group",
					"supplier_group_name": name,
					"parent_supplier_group": parent,
					"is_group": 0,
				}
			).insert(ignore_permissions=True)
		except Exception:
			# usar el primero disponible
			existing = frappe.db.get_value("Supplier Group", {}, "name")
			return existing or name
	return name


def ensure_finance_suppliers() -> list[str]:
	created: list[str] = []
	if not frappe.db.exists("DocType", "Supplier"):
		return created

	default_group = (
		frappe.db.get_single_value("Buying Settings", "supplier_group")
		or frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
		or "All Supplier Groups"
	)

	for supplier_name, group_hint in FINANCE_SUPPLIERS:
		if frappe.db.exists("Supplier", supplier_name):
			continue
		if frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name"):
			continue
		group = (
			_ensure_supplier_group(group_hint)
			if frappe.db.exists("Supplier Group", group_hint)
			else default_group
		)
		try:
			doc = frappe.get_doc(
				{
					"doctype": "Supplier",
					"supplier_name": supplier_name,
					"supplier_group": group,
					"supplier_type": "Company",
				}
			)
			doc.insert(ignore_permissions=True)
			created.append(doc.name)
		except Exception as exc:
			frappe.log_error(title="seed_finance_suppliers", message=str(exc))
	return created


def ensure_finance_custom_fields() -> None:
	"""Custom Field club_concepto en Purchase Invoice y Sales Invoice."""
	for dt, insert_after in (
		("Purchase Invoice", "due_date"),
		("Sales Invoice", "due_date"),
	):
		if not frappe.db.exists("DocType", dt):
			continue
		name = f"{dt}-club_concepto"
		if frappe.db.exists("Custom Field", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Custom Field",
				"name": name,
				"dt": dt,
				"fieldname": "club_concepto",
				"label": "Concepto Club",
				"fieldtype": "Select",
				"options": "\nPersonal\nDeportiva\nInfraestructura\nEstructura",
				"insert_after": insert_after,
			}
		).insert(ignore_permissions=True)


def run_seed_finance_masters() -> dict[str, Any]:
	"""Orquesta custom fields, suppliers e ítems."""
	try:
		company = resolve_icdpe_company()
	except Exception:
		return {"skipped": True, "reason": "company"}

	# PI de servicios: sin inventario perpetuo si falta cuenta stock
	if frappe.db.get_value("Company", company, "enable_perpetual_inventory"):
		stock_rbnb = frappe.db.get_value("Company", company, "stock_received_but_not_billed")
		if not stock_rbnb or not frappe.db.exists("Account", stock_rbnb):
			frappe.db.set_value(
				"Company",
				company,
				"enable_perpetual_inventory",
				0,
				update_modified=False,
			)

	ensure_finance_custom_fields()
	suppliers = ensure_finance_suppliers()
	items = run_finance_items_seed()
	return {"suppliers_created": suppliers, "items": items}
