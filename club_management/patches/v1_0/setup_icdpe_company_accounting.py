"""Completa defaults contables ICDPE + ítems de servicio."""

from __future__ import annotations

import frappe

from club_management.setup.icdpe_company_accounts import setup_icdpe_company_accounting


def execute() -> None:
	if not frappe.db.exists("Company", "Institución Cultural y Deportiva Pedro Echagüe"):
		return
	setup_icdpe_company_accounting(create_items=True)
