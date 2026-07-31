"""Tests corrección de número de socio (spec corregir_numero_socio.md)."""

from __future__ import annotations

import frappe

from club_management.members.api.socio_operaciones_desk import (
	corregir_numero_socio as corregir_numero_socio_api,
)
from club_management.members.services.corregir_numero_socio import corregir_numero_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	make_secretaria_user,
)


class TestCorregirNumeroSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = make_secretaria_user("secretaria.renum@example.com")

	def test_corrige_numero_provisional_a_libre(self) -> None:
		socio = insert_socio(dni="88112201", email="renum.ok@example.com", numero_socio=991239)
		frappe.set_user(self._secretaria)
		try:
			nuevo = corregir_numero_socio(socio.name, 995001)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(nuevo, "995001")
		self.assertFalse(frappe.db.exists("Socio", "991239"))
		self.assertTrue(frappe.db.exists("Socio", "995001"))
		self.assertEqual(int(frappe.db.get_value("Socio", "995001", "numero_socio")), 995001)

	def test_destino_ocupado_falla(self) -> None:
		insert_socio(dni="88112202", email="renum.dest@example.com", numero_socio=995002)
		socio = insert_socio(dni="88112203", email="renum.src@example.com", numero_socio=991240)
		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				corregir_numero_socio(socio.name, 995002)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("Socio", "991240"))

	def test_mismo_numero_es_noop(self) -> None:
		socio = insert_socio(dni="88112204", email="renum.same@example.com", numero_socio=991241)
		frappe.set_user(self._secretaria)
		try:
			nuevo = corregir_numero_socio(socio.name, 991241)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(nuevo, "991241")
		self.assertEqual(int(frappe.db.get_value("Socio", "991241", "numero_socio")), 991241)

	def test_api_requiere_secretaria(self) -> None:
		socio = insert_socio(dni="88112205", email="renum.perm@example.com", numero_socio=991242)
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				corregir_numero_socio_api(socio=socio.name, nuevo_numero=996001)
		finally:
			frappe.set_user("Administrator")
