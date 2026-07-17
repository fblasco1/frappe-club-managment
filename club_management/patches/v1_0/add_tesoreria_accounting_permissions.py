"""Patch: permisos de lectura contable para rol Tesoreria."""

from __future__ import annotations

import frappe

from club_management.finance.permissions import ROLE_TESORERIA, ensure_role_tesoreria_exists

# DocTypes ERPNext de solo lectura para Tesorería (sin create/write/delete).
READ_ONLY_DOCTYPES: tuple[str, ...] = (
	"Account",
	"Cost Center",
	"GL Entry",
	"Sales Invoice",
	"Purchase Invoice",
	"Payment Entry",
	"Journal Entry",
	"Customer",
	"Supplier",
	"Item",
	"Mode of Payment",
	"Company",
)


def _ensure_read_perm(doctype: str, role: str) -> None:
	if not frappe.db.exists("DocType", doctype):
		return
	existing = frappe.db.exists(
		"Custom DocPerm",
		{"parent": doctype, "role": role, "permlevel": 0},
	)
	if existing:
		return
	# También puede existir DocPerm estándar
	if frappe.db.exists("DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		return
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			"read": 1,
			"write": 0,
			"create": 0,
			"delete": 0,
			"submit": 0,
			"cancel": 0,
			"amend": 0,
			"report": 1,
			"export": 1,
			"share": 0,
			"print": 1,
			"email": 0,
		}
	).insert(ignore_permissions=True)


def execute() -> None:
	ensure_role_tesoreria_exists()
	for dt in READ_ONLY_DOCTYPES:
		_ensure_read_perm(dt, ROLE_TESORERIA)
	frappe.clear_cache()
