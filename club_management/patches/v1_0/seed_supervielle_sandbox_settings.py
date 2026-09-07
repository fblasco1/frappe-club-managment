"""Semilla sandbox de Supervielle Settings (sin secret_key)."""

from __future__ import annotations

import frappe

from club_management.integrations.supervielle.payload import (
	SANDBOX_API_URL,
	SANDBOX_CONCEPTO,
	SANDBOX_CUIT,
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
	settings.sandbox_mode = 1
	settings.save(ignore_permissions=True)
