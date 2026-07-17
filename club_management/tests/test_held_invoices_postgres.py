"""Tests parche PostgreSQL get_held_invoices (CURDATE → CURRENT_DATE)."""

from __future__ import annotations

import frappe

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.test_helpers import MembersTestCase


class TestHeldInvoicesPostgres(MembersTestCase):
	def test_get_held_invoices_no_usa_curdate(self) -> None:
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not frappe.db.exists("DocType", "Purchase Invoice"):
			self.skipTest("ERPNext no instalado")

		apply_patch()
		import erpnext.accounts.utils as accounts_utils

		self.assertTrue(getattr(accounts_utils, "_club_held_invoices_pg_patch", False))
		# No debe lanzar por CURDATE()
		result = accounts_utils.get_held_invoices("Supplier", "Any")
		self.assertTrue(result is None or isinstance(result, set))
