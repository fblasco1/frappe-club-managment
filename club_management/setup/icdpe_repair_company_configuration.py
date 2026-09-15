"""Repara links rotos de Company ICDPE tras importar plan de cuentas.

Evita errores al guardar Company / Setup Wizard:
- referencias a cuentas del plan viejo eliminado
- inventario perpetuo sin cuentas Stock
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_company_accounts import ACCOUNTS, setup_icdpe_company_accounting

OPTIONAL_ACCOUNT_DEFAULTS: dict[str, str] = {
	"default_payable_account": "2110 - Proveedores - ICDPE",
	"accumulated_depreciation_account": "129001 - Amort. acum. Inmuebles - ICDPE",
	"depreciation_expense_account": "581001 - Amortizaciones - ICDPE",
	"default_provisional_account": "115001 - Anticipos / gastos pagados por adelantado - ICDPE",
	"round_off_cost_center": "Administración - ICDPE",
	"depreciation_cost_center": "Administración - ICDPE",
}


def _broken_company_links(company: str) -> dict[str, str | None]:
	meta = frappe.get_meta("Company")
	broken: dict[str, str | None] = {}
	doc = frappe.get_doc("Company", company)
	for field in meta.fields:
		if field.fieldtype != "Link" or field.options not in ("Account", "Cost Center"):
			continue
		value = doc.get(field.fieldname)
		if value and not frappe.db.exists(field.options, value):
			broken[field.fieldname] = value
	return broken


def _clear_broken_company_links(company: str) -> list[str]:
	broken = _broken_company_links(company)
	if not broken:
		return []
	updates = {field: None for field in broken}
	frappe.db.set_value("Company", company, updates, update_modified=False)
	return list(broken.keys())


def _repair_mode_of_payment_accounts(company: str) -> int:
	fixed = 0
	for mop_name in frappe.get_all("Mode of Payment", pluck="name"):
		mop = frappe.get_doc("Mode of Payment", mop_name)
		changed = False
		for row in mop.accounts or []:
			if row.company != company or not row.default_account:
				continue
			if not frappe.db.exists("Account", row.default_account):
				row.default_account = None
				changed = True
				fixed += 1
		if changed:
			mop.save(ignore_permissions=True)
	return fixed


def _apply_optional_defaults(company: str) -> dict[str, str]:
	applied: dict[str, str] = {}
	for field, account_or_cc in OPTIONAL_ACCOUNT_DEFAULTS.items():
		meta_field = frappe.get_meta("Company").get_field(field)
		if not meta_field:
			continue
		target_doctype = meta_field.options
		if not frappe.db.exists(target_doctype, account_or_cc):
			continue
		current = frappe.db.get_value("Company", company, field)
		if current:
			continue
		frappe.db.set_value("Company", company, field, account_or_cc, update_modified=False)
		applied[field] = account_or_cc
	return applied


def run(*, create_items: bool = False) -> dict[str, Any]:
	"""Limpia links rotos y re-aplica defaults ICDPE sin inventario perpetuo."""
	company = resolve_icdpe_company()
	broken_fields = _clear_broken_company_links(company)
	frappe.db.set_value(
		"Company",
		company,
		"enable_perpetual_inventory",
		0,
		update_modified=False,
	)
	mop_fixed = _repair_mode_of_payment_accounts(company)
	setup = setup_icdpe_company_accounting(create_items=create_items)
	optional = _apply_optional_defaults(company)
	frappe.db.commit()

	return {
		"company": company,
		"broken_fields_cleared": broken_fields,
		"mode_of_payment_rows_cleared": mop_fixed,
		"optional_defaults_applied": optional,
		"setup": setup,
	}
