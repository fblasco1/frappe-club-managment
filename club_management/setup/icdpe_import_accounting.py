"""Importa plan de cuentas ICDPE, centros de costo e ítems de servicio."""

from __future__ import annotations

import csv
import os
from typing import Any

import frappe
from frappe import _

from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_company_accounts import setup_icdpe_company_accounting
from erpnext.accounts.doctype.account.chart_of_accounts.chart_of_accounts import create_charts
from erpnext.accounts.doctype.chart_of_accounts_importer.chart_of_accounts_importer import (
	build_forest,
	set_default_accounts,
	unset_existing_data,
)


def _read_coa_csv(path: str) -> list[list[str]]:
	with open(path, encoding="utf-8") as handle:
		rows = list(csv.reader(handle))
	if not rows:
		frappe.throw(_("El CSV del plan de cuentas está vacío: {0}").format(path))

	data: list[list[str]] = []
	for row in rows[1:]:
		if not row:
			continue
		if not row[1] and len(row) > 1:
			row[1] = row[0]
			row[3] = row[2]
		data.append(row)
	return data


def import_chart_of_accounts(coa_csv_path: str, *, company: str | None = None) -> int:
	"""Reemplaza el plan de cuentas de la compañía con el CSV ICDPE."""
	if not os.path.isfile(coa_csv_path):
		frappe.throw(_("No existe el archivo: {0}").format(coa_csv_path))

	company = company or resolve_icdpe_company()
	data = _read_coa_csv(coa_csv_path)

	unset_existing_data(company)
	frappe.local.flags.ignore_root_company_validation = True
	forest = build_forest(data)
	create_charts(company, custom_chart=forest, from_coa_importer=True)
	set_default_accounts(company)

	return frappe.db.count("Account", {"company": company})


def _normalize_company_field(value: str, company: str) -> str:
	"""Acepta CSV con o sin acento en «Institución»."""
	if not value:
		return value
	for alias in (
		"Institución Cultural y Deportiva Pedro Echagüe",
		"Institucion Cultural y Deportiva Pedro Echagüe",
	):
		if value == alias:
			return company
	return value


def _read_cost_center_rows(path: str, company: str) -> list[dict[str, str]]:
	with open(path, encoding="utf-8") as handle:
		reader = csv.DictReader(handle)
		rows: list[dict[str, str]] = []
		for row in reader:
			ident = (row.get("Identificador") or row.get("cost_center_name") or "").strip()
			if not ident:
				continue
			parent = (
				row.get("Centro de costos principal")
				or row.get("parent_cost_center")
				or ""
			).strip()
			rows.append(
				{
					"name": ident,
					"cost_center_name": (
						row.get("Nombre del centro de costos") or row.get("cost_center_name") or ident
					).strip(),
					"parent_cost_center": _normalize_company_field(parent, company),
					"company": company,
					"is_group": str(row.get("Es un grupo") or row.get("is_group") or "0").strip(),
					"disabled": str(row.get("Deshabilitado") or "0").strip(),
				}
			)
		return rows


def _delete_company_cost_centers(company: str) -> int:
	rows = frappe.get_all(
		"Cost Center",
		filters={"company": company},
		fields=["name"],
		order_by="lft desc",
	)
	for row in rows:
		frappe.delete_doc("Cost Center", row.name, force=1, ignore_permissions=True)
	return len(rows)


def import_cost_centers(
	*csv_paths: str,
	company: str | None = None,
	replace_existing: bool = True,
) -> dict[str, Any]:
	"""Importa centros de costo ICDPE (grupos y luego subcentros)."""
	company = company or resolve_icdpe_company()
	deleted = _delete_company_cost_centers(company) if replace_existing else 0

	created: list[str] = []
	skipped: list[str] = []
	name_map: dict[str, str] = {}

	for path in csv_paths:
		if not os.path.isfile(path):
			frappe.throw(_("No existe el archivo: {0}").format(path))
		for row in _read_cost_center_rows(path, company):
			if frappe.db.exists("Cost Center", row["name"]):
				skipped.append(row["name"])
				name_map[row["name"]] = row["name"]
				continue

			parent = row["parent_cost_center"] or None
			cost_center_name = row["cost_center_name"]
			if not parent:
				cost_center_name = company
				parent = None
			elif parent in name_map:
				parent = name_map[parent]

			doc = frappe.get_doc(
				{
					"doctype": "Cost Center",
					"cost_center_name": cost_center_name,
					"parent_cost_center": parent,
					"company": company,
					"is_group": int(row["is_group"] or 0),
					"disabled": int(row["disabled"] or 0),
				}
			)
			if not parent:
				doc.flags.ignore_mandatory = True
			doc.insert(ignore_permissions=True)
			actual_name = doc.name
			if parent and row["name"] != actual_name:
				frappe.rename_doc(
					"Cost Center",
					actual_name,
					row["name"],
					force=True,
					ignore_permissions=True,
				)
				actual_name = row["name"]
			name_map[row["name"]] = actual_name
			created.append(actual_name)

	return {
		"company": company,
		"deleted": deleted,
		"created": created,
		"skipped": skipped,
		"total": frappe.db.count("Cost Center", {"company": company}),
	}


def run(
	coa_csv_path: str,
	cost_center_csv_paths: list[str] | None = None,
	*,
	create_items: bool = True,
) -> dict[str, Any]:
	"""Orquesta importación contable ICDPE (idempotente en ítems/defaults)."""
	company = resolve_icdpe_company()
	accounts = import_chart_of_accounts(coa_csv_path, company=company)
	frappe.db.commit()

	cc_paths = cost_center_csv_paths or []
	cc_result = (
		import_cost_centers(*cc_paths, company=company)
		if cc_paths
		else {"company": company, "total": frappe.db.count("Cost Center", {"company": company})}
	)
	frappe.db.commit()

	setup_result = setup_icdpe_company_accounting(create_items=create_items)
	frappe.db.commit()

	return {
		"company": company,
		"accounts": accounts,
		"cost_centers": cc_result,
		"setup": setup_result,
	}
