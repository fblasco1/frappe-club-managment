"""Tests ítems financieros y resolución de Cost Center."""

from __future__ import annotations

import frappe

from club_management.finance.services.carga_rapida import (
	resolve_buying_cost_center,
	resolve_selling_cost_center,
)
from club_management.finance.setup.icdpe_finance_items import (
	EXPENSE_SPECS,
	INCOME_SPECS,
	run_finance_items_seed,
)
from club_management.finance.setup.seed_finance_masters import run_seed_finance_masters
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestItemsFinanceCostCenter(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		try:
			self.company = resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		run_seed_finance_masters()

	def test_seed_crea_items_ingreso(self) -> None:
		counts = run_finance_items_seed()
		self.assertIn(counts["created"] + counts["updated"] + counts["skipped"], range(0, 100))
		# Al menos un ingreso típico si hay cuentas
		created_any = any(frappe.db.exists("Item", s.item_code) for s in INCOME_SPECS)
		if counts["skipped"] == len(INCOME_SPECS) + len(EXPENSE_SPECS):
			self.skipTest("Todas las cuentas/CC faltan en el sitio")
		self.assertTrue(created_any or counts["updated"] > 0)

	def test_resolve_selling_cost_center_desde_item(self) -> None:
		if not frappe.db.exists("Item", "ICDPE-FIN-BUFFET"):
			self.skipTest("Ítem buffet no sembrado")
		cc = resolve_selling_cost_center("ICDPE-FIN-BUFFET", self.company)
		self.assertTrue(cc)
		self.assertTrue(frappe.db.exists("Cost Center", cc))

	def test_resolve_buying_cost_center_desde_item(self) -> None:
		if not frappe.db.exists("Item", "ICDPE-FIN-SUELDOS"):
			self.skipTest("Ítem sueldos no sembrado")
		cc = resolve_buying_cost_center("ICDPE-FIN-SUELDOS", self.company)
		self.assertTrue(cc)

	def test_sin_cc_falla(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			resolve_selling_cost_center("ITEM-INEXISTENTE-XYZ", self.company)
