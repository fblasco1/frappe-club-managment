"""Completa configuración no secreta incorporada por Botón de Pago v2.6."""

from __future__ import annotations

import frappe

from club_management.integrations.supervielle.payload import SANDBOX_RENDITION_URL


def execute() -> None:
	if not frappe.db.exists("DocType", "Supervielle Settings"):
		return
	if not frappe.db.exists("Mode of Payment", "Cobros Plus (ARS)"):
		frappe.get_doc(
			{
				"doctype": "Mode of Payment",
				"mode_of_payment": "Cobros Plus (ARS)",
				"type": "Bank",
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
	settings = frappe.get_single("Supervielle Settings")
	settings.url_ok = settings.url_ok or "https://gestion.icdpedroechague.com.ar/pago-ok"
	settings.url_error = settings.url_error or "https://gestion.icdpedroechague.com.ar/pago-error"
	settings.convenio = settings.convenio or "TODOS"
	settings.rendicion_api_url = settings.rendicion_api_url or SANDBOX_RENDITION_URL
	settings.mode_of_payment = settings.mode_of_payment or "Cobros Plus (ARS)"
	clearing_account = frappe.db.get_value(
		"Account",
		{"account_number": "115002", "is_group": 0},
		"name",
	)
	current_type = (
		frappe.db.get_value("Account", settings.clearing_account, "account_type")
		if settings.clearing_account
		else None
	)
	if clearing_account and (not settings.clearing_account or current_type == "Expense Account"):
		settings.clearing_account = clearing_account
	settings.save(ignore_permissions=True)
