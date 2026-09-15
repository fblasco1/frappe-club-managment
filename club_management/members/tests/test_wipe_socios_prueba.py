"""Tests del reset de socios de prueba (solo dry_run)."""

from __future__ import annotations

import frappe

from club_management.members.setup.wipe_socios_prueba import wipe_socios_prueba
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestWipeSociosPrueba(MembersTestCase):
	def test_dry_run_no_borra_socios(self) -> None:
		socio = insert_socio(dni="50999001", email="wipe.test@example.com")
		stats = wipe_socios_prueba(dry_run=True)
		self.assertGreaterEqual(stats.socios, 1)
		self.assertTrue(frappe.db.exists("Socio", socio.name))
