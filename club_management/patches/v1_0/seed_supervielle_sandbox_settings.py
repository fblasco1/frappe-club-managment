"""Semilla sandbox de Supervielle Settings (sin secret_key)."""

from __future__ import annotations

import frappe

from club_management.integrations.supervielle.payload import (
	SANDBOX_API_URL,
	SANDBOX_CONCEPTO,
	SANDBOX_CUIT,
	SANDBOX_RENDITION_URL,
)


def execute() -> None:
	if not frappe.db.exists("DocType", "Supervielle Settings"):
		return
	try:
		settings = frappe.get_single("Supervielle Settings")
	except frappe.DoesNotExistError:
		settings = frappe.new_doc("Supervielle Settings")
	if not settings.cuit_emisor:
		settings.cuit_emisor = SANDBOX_CUIT
	if not settings.api_url:
		settings.api_url = SANDBOX_API_URL
	if not settings.concepto_default:
		settings.concepto_default = SANDBOX_CONCEPTO
	if not settings.url_ok:
		settings.url_ok = "https://gestion.icdpedroechague.com.ar/pago-ok"
	if not settings.url_error:
		settings.url_error = "https://gestion.icdpedroechague.com.ar/pago-error"
	if not settings.convenio:
		settings.convenio = "TODOS"
	if not settings.rendicion_api_url:
		settings.rendicion_api_url = SANDBOX_RENDITION_URL
	if not settings.mode_of_payment:
		settings.mode_of_payment = "Cobros Plus (ARS)"
	settings.sandbox_mode = 1
	settings.save(ignore_permissions=True)
