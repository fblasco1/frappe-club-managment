"""Consolida cuota social en un solo ítem: ICDPE-CUOTA-SOCIAL (local/prod ops)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

CANONICAL_ITEM = "ICDPE-CUOTA-SOCIAL"
LEGACY_ITEM = "CLUB-Cuota-Social-Base"
CANONICAL_NAME = "Cuota social"


def _sync_ple_invoice(invoice_name: str, amount: float | None = None) -> bool:
	"""Alinea la fila PLE de la SI (voucher_no = against_voucher) con su grand_total."""
	target = flt(
		amount
		if amount is not None
		else frappe.db.get_value("Sales Invoice", invoice_name, "grand_total"),
		2,
	)
	rows = frappe.db.sql(
		"""
		SELECT name, amount_in_account_currency
		FROM "tabPayment Ledger Entry"
		WHERE voucher_no = %s AND against_voucher_no = %s AND delinked = 0
		""",
		(invoice_name, invoice_name),
		as_dict=True,
	)
	if not rows:
		return False
	changed = False
	for row in rows:
		if abs(flt(row.amount_in_account_currency) - target) > 0.005:
			frappe.db.set_value(
				"Payment Ledger Entry",
				row.name,
				{"amount": target, "amount_in_account_currency": target},
				update_modified=False,
			)
			changed = True
	return changed


def sync_ple_cuota_mismatch(*, dry_run: bool = False) -> dict:
	"""Corrige PLE desincronizado tras migración/parche de cuota social."""
	rows = frappe.db.sql(
		"""
		SELECT si.name, si.grand_total, si.outstanding_amount
		FROM "tabSales Invoice" si
		WHERE si.docstatus = 1
		  AND si.outstanding_amount > 0
		  AND EXISTS (
		    SELECT 1 FROM "tabSales Invoice Item" sii
		    WHERE sii.parent = si.name AND sii.item_code = %s
		  )
		""",
		(CANONICAL_ITEM,),
		as_dict=True,
	)
	fixed: list[str] = []
	for row in rows:
		target = flt(row.grand_total, 2)
		if dry_run:
			ple = frappe.db.sql(
				"""
				SELECT amount_in_account_currency FROM "tabPayment Ledger Entry"
				WHERE voucher_no = %s AND against_voucher_no = %s AND delinked = 0 LIMIT 1
				""",
				(row.name, row.name),
			)
			if ple and abs(flt(ple[0][0]) - target) > 0.005:
				fixed.append(row.name)
			continue
		if _sync_ple_invoice(row.name, target):
			fixed.append(row.name)
	return {"dry_run": dry_run, "fixed_count": len(fixed), "invoices": fixed[:50]}


def _table_has_field(doctype: str, fieldname: str) -> bool:
	return bool(frappe.get_meta(doctype).has_field(fieldname))


def _migrate_references(*, dry_run: bool) -> dict[str, int]:
	"""Reemplaza LEGACY_ITEM por CANONICAL_ITEM en tablas conocidas."""
	updates: dict[str, int] = {}

	si_count = frappe.db.count("Sales Invoice Item", {"item_code": LEGACY_ITEM})
	updates["sales_invoice_item"] = si_count
	if not dry_run and si_count:
		frappe.db.sql(
			"""
			UPDATE `tabSales Invoice Item`
			SET item_code = %s, item_name = %s
			WHERE item_code = %s
			""",
			(CANONICAL_ITEM, CANONICAL_NAME, LEGACY_ITEM),
		)

	for doctype, field in (
		("Subscription Plan Item", "item"),
		("Subscription Item", "item"),
		("Sales Order Item", "item_code"),
		("Quotation Item", "item_code"),
	):
		if not frappe.db.exists("DocType", doctype) or not _table_has_field(doctype, field):
			continue
		count = frappe.db.count(doctype, {field: LEGACY_ITEM})
		key = f"{doctype}.{field}"
		updates[key] = count
		if not dry_run and count:
			frappe.db.sql(
				f"UPDATE `tab{doctype}` SET `{field}` = %s WHERE `{field}` = %s",
				(CANONICAL_ITEM, LEGACY_ITEM),
			)

	child = "Club Settings Cuota Categoria"
	if frappe.db.exists("DocType", child):
		count = frappe.db.count(child, {"item": LEGACY_ITEM})
		updates["club_settings_cuotas"] = count
		if not dry_run and count:
			frappe.db.sql(
				f"UPDATE `tab{child}` SET item = %s WHERE item = %s",
				(CANONICAL_ITEM, LEGACY_ITEM),
			)

	return updates


def run(*, dry_run: bool = False, confirm: str = "") -> dict:
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	if not frappe.db.exists("Item", CANONICAL_ITEM):
		frappe.throw(f"Falta el ítem {CANONICAL_ITEM}. Ejecute setup ICDPE.")

	from club_management.setup.icdpe_company_accounts import sync_club_settings_item_cuota

	before = {
		"sales_invoice_item": frappe.db.count("Sales Invoice Item", {"item_code": LEGACY_ITEM}),
		"canonical_si": frappe.db.count("Sales Invoice Item", {"item_code": CANONICAL_ITEM}),
		"item_cuota_social": frappe.db.get_single_value("Club Settings", "item_cuota_social"),
	}

	if not dry_run:
		sync_club_settings_item_cuota()

	updates = _migrate_references(dry_run=dry_run)

	ple_sync: dict | None = None
	if not dry_run:
		ple_sync = sync_ple_cuota_mismatch(dry_run=False)

	if not dry_run:
		frappe.db.commit()

	after = {
		"sales_invoice_item_legacy": frappe.db.count("Sales Invoice Item", {"item_code": LEGACY_ITEM}),
		"sales_invoice_item_canonical": frappe.db.count(
			"Sales Invoice Item", {"item_code": CANONICAL_ITEM}
		),
		"item_cuota_social": frappe.db.get_single_value("Club Settings", "item_cuota_social"),
	}

	return {
		"dry_run": dry_run,
		"canonical_item": CANONICAL_ITEM,
		"legacy_item": LEGACY_ITEM,
		"before": before,
		"updates": updates,
		"ple_sync": ple_sync,
		"after": after,
	}
