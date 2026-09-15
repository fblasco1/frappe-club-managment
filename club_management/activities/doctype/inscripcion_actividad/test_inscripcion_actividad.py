"""Tests del DocType Inscripcion Actividad."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestInscripcionActividad(MembersTestCase):
	def test_no_duplica_inscripcion_activa(self) -> None:
		if not frappe.db.exists("Actividad", "Tenis"):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": "Tenis", "habilitada": 1}
			).insert(ignore_permissions=True)

		socio = insert_socio(dni="70992001", email="ins.dup@example.com", estado="Activo")
		doc = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": "Tenis",
				"estado": "Activa",
			}
		)
		doc.insert(ignore_permissions=True)

		dup = frappe.copy_doc(doc)
		dup.name = None
		with self.assertRaises(frappe.ValidationError):
			dup.insert(ignore_permissions=True)
