"""Tests gate apply masivo local vs prod.

Spec: `club_management/specs/carga_masiva_cobranzas.md`
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.scripts.bulk_io import (
	CONFIRM_LOCAL,
	CONFIRM_PROD,
	ensure_bulk_apply_allowed,
	is_production_site,
)


class TestBulkApplyConfirm(FrappeTestCase):
	def test_dry_run_no_exige_confirm(self) -> None:
		ensure_bulk_apply_allowed(dry_run=True, confirm="")

	def test_prod_exige_apply_prod(self) -> None:
		original = frappe.local.site
		try:
			frappe.local.site = "gestion.icdpedroechague.com.ar"
			self.assertTrue(is_production_site())
			with self.assertRaises(frappe.ValidationError):
				ensure_bulk_apply_allowed(dry_run=False, confirm="")
			with self.assertRaises(frappe.ValidationError):
				ensure_bulk_apply_allowed(dry_run=False, confirm=CONFIRM_LOCAL)
			ensure_bulk_apply_allowed(dry_run=False, confirm=CONFIRM_PROD)
		finally:
			frappe.local.site = original

	def test_local_exige_local_dev(self) -> None:
		original = frappe.local.site
		try:
			frappe.local.site = "dev.localhost"
			self.assertFalse(is_production_site())
			with self.assertRaises(frappe.ValidationError):
				ensure_bulk_apply_allowed(dry_run=False, confirm="")
			with self.assertRaises(frappe.ValidationError):
				ensure_bulk_apply_allowed(dry_run=False, confirm=CONFIRM_PROD)
			ensure_bulk_apply_allowed(dry_run=False, confirm=CONFIRM_LOCAL)
		finally:
			frappe.local.site = original
