"""Tests inscripción de actividades desde Desk (Secretaría)."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.activities.services.inscripcion_socio import inscribir_actividades_desk
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestSocioInscripcionDesk(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = "secretaria_insc@example.com"
		if not frappe.db.exists("User", self._secretaria):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			).insert(ignore_permissions=True)

	def _ensure_zumba(self) -> str:
		if frappe.db.exists("Actividad", "Zumba"):
			return "Zumba"
		doc = frappe.get_doc(
			{
				"doctype": "Actividad",
				"name": "Zumba",
				"titulo": "Zumba",
				"habilitada": 1,
				"usa_grupos": 0,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_inscribir_desde_pendiente_inscripcion_activa_socio(self) -> None:
		zumba = self._ensure_zumba()
		socio = insert_socio()
		cambiar_estado(socio.name, ESTADO_SOCIO_PENDIENTE_INSCRIPCION, motivo="Test")
		frappe.set_user(self._secretaria)
		try:
			result = inscribir_actividades_desk(
				socio.name,
				[{"actividad": zumba}],
			)
		finally:
			frappe.set_user("Administrator")
		self.assertIn("Zumba", result["actividad_resumen"])
		socio.reload()
		self.assertEqual(socio.estado, "Activo")
		self.assertTrue(
			frappe.db.exists(
				"Inscripcion Actividad",
				{"socio": socio.name, "actividad": zumba, "estado": "Activa"},
			)
		)
