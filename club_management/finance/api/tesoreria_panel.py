"""API Desk: panel operativo de Tesorería (GF-6)."""

from __future__ import annotations

import frappe

from club_management.finance.services import tesoreria_panel


@frappe.whitelist()
def get_panel_data() -> dict:
	"""Listas del panel de Tesorería (OC pendientes, FC pagas, cobros)."""
	return tesoreria_panel.get_panel_data()
