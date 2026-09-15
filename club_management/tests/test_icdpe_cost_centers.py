"""Tests centros de costo ICDPE requeridos por ítems de servicio."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.setup.basquet_cost_center import BASQUET_COST_CENTER, BASQUET_COST_CENTER_PARENT
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_company_accounts import ensure_missing_cost_centers


class TestIcdpeCostCenters(MembersTestCase):
	def test_ensure_missing_cost_centers_crea_basquet_unificado(self) -> None:
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada en el sitio")
		if not frappe.db.exists("Cost Center", BASQUET_COST_CENTER_PARENT):
			self.skipTest("Falta CC padre Deportes - ICDPE")

		if frappe.db.exists("Cost Center", BASQUET_COST_CENTER):
			frappe.delete_doc("Cost Center", BASQUET_COST_CENTER, force=1)

		created = ensure_missing_cost_centers()
		self.assertIn(BASQUET_COST_CENTER, created)
		self.assertTrue(frappe.db.exists("Cost Center", BASQUET_COST_CENTER))
