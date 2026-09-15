"""Tests de integridad referencial: `Socio.solicitud_origen` → `Solicitud Asociacion`.

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 6).
"""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	insert_solicitud_asociacion,
)


class TestSocioReferenciaSolicitud(MembersTestCase):
	def test_socio_solicitud_origen_link_a_solicitud(self) -> None:
		sol = insert_solicitud_asociacion(dni="60111001", email="ref1@example.com")
		socio = insert_socio(
			dni="60111002",
			email="socio.ref1@example.com",
			solicitud_origen=sol.name,
		)
		self.assertEqual(socio.solicitud_origen, sol.name)
		ref = frappe.get_doc("Solicitud Asociacion", socio.solicitud_origen)
		self.assertEqual(ref.name, sol.name)

	def test_socio_solicitud_origen_invalida_falla(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			insert_socio(
				dni="60111003",
				email="socio.ref2@example.com",
				solicitud_origen="SOL-DOES-NOT-EXIST",
			)

