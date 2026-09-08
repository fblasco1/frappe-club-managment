"""Tests del seed de espacios."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.seed import ESPACIOS_SEED, ensure_espacios_catalogo


class TestSeedEspacios(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_seed_crea_catalogo_e_idempotente(self) -> None:
		first = ensure_espacios_catalogo()
		self.assertEqual(len(first), len(ESPACIOS_SEED))
		for titulo, tipo, alquilable in ESPACIOS_SEED:
			self.assertTrue(frappe.db.exists("Espacio", titulo))
			row = frappe.db.get_value(
				"Espacio",
				titulo,
				["tipo", "alquilable", "habilitado"],
				as_dict=True,
			)
			self.assertEqual(row.tipo, tipo)
			self.assertEqual(int(row.alquilable), alquilable)
			self.assertEqual(int(row.habilitado), 1)

		second = ensure_espacios_catalogo()
		self.assertEqual(second, first)
		self.assertEqual(
			frappe.db.count("Espacio", {"titulo": ("in", [t for t, _, _ in ESPACIOS_SEED])}),
			len(ESPACIOS_SEED),
		)
