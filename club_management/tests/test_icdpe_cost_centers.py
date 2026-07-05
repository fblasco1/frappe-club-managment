"""Tests centros de costo ICDPE requeridos por ítems de servicio."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_company_accounts import ensure_missing_cost_centers

BASQUET_ESCUELITA_CC = "Deportes - Basquet Escuelita - ICDPE"


class TestIcdpeCostCenters(MembersTestCase):
	def test_ensure_missing_cost_centers_crea_basquet_escuelita(self) -> None:
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada en el sitio")
		if not frappe.db.exists("Cost Center", "Deportes - ICDPE"):
			self.skipTest("Falta CC padre Deportes - ICDPE")

		if frappe.db.exists("Cost Center", BASQUET_ESCUELITA_CC):
			frappe.delete_doc("Cost Center", BASQUET_ESCUELITA_CC, force=1)

		created = ensure_missing_cost_centers()
		self.assertIn(BASQUET_ESCUELITA_CC, created)
		self.assertTrue(frappe.db.exists("Cost Center", BASQUET_ESCUELITA_CC))
