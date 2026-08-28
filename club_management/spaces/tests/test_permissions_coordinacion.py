"""Tests de permisos Coordinacion / Tesoreria / Socio para Spaces."""

from __future__ import annotations

import frappe

from club_management.members.permissions_app import has_app_permission
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user
from club_management.spaces.permissions import (
	ROLE_COORDINACION,
	ensure_role_coordinacion_exists,
)
from club_management.spaces.helpers import (
	insert_espacio,
	make_coordinacion_user,
	make_socio_portal_user,
	make_tesoreria_user,
)


class TestPermissionsCoordinacion(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_coordinacion_exists()

	def test_ensure_role_coordinacion_crea_rol_con_desk(self) -> None:
		ensure_role_coordinacion_exists()
		self.assertTrue(frappe.db.exists("Role", ROLE_COORDINACION))
		self.assertEqual(frappe.db.get_value("Role", ROLE_COORDINACION, "desk_access"), 1)

	def test_coordinacion_escribe_espacio(self) -> None:
		user = make_coordinacion_user("coord.write@example.com")
		frappe.set_user(user)
		try:
			self.assertTrue(frappe.has_permission("Espacio", ptype="create"))
			self.assertTrue(frappe.has_permission("Espacio", ptype="write"))
			self.assertTrue(frappe.has_permission("Reserva Espacio", ptype="create"))
			self.assertTrue(has_app_permission())
		finally:
			frappe.set_user("Administrator")

	def test_tesoreria_solo_lectura(self) -> None:
		user = make_tesoreria_user("tesoreria.spaces.read@example.com")
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role == "Tesoreria"]
		doc.save(ignore_permissions=True)

		frappe.set_user(user)
		try:
			self.assertTrue(frappe.has_permission("Espacio", ptype="read"))
			self.assertFalse(frappe.has_permission("Espacio", ptype="create"))
			self.assertFalse(frappe.has_permission("Espacio", ptype="write"))
			self.assertFalse(frappe.has_permission("Reserva Espacio", ptype="create"))
			self.assertTrue(has_app_permission())
		finally:
			frappe.set_user("Administrator")

	def test_socio_sin_desk_spaces(self) -> None:
		user = make_socio_portal_user("socio.spaces.deny@example.com")
		frappe.set_user(user)
		try:
			self.assertFalse(frappe.has_permission("Espacio", ptype="create"))
			self.assertFalse(frappe.has_permission("Espacio", ptype="write"))
			self.assertFalse(frappe.has_permission("Reserva Espacio", ptype="create"))
			self.assertFalse(has_app_permission())
		finally:
			frappe.set_user("Administrator")

	def test_secretaria_tambien_escribe(self) -> None:
		user = make_secretaria_user("secretaria.spaces@example.com")
		frappe.set_user(user)
		try:
			self.assertTrue(frappe.has_permission("Espacio", ptype="create"))
			self.assertTrue(frappe.has_permission("Reserva Espacio", ptype="write"))
		finally:
			frappe.set_user("Administrator")

	def test_workspace_espacios_incluye_coordinacion(self) -> None:
		# El workspace se siembra en migrate; no re-sincronizar aquí (import_file
		# puede hacer commit y romper el savepoint del test).
		if not frappe.db.exists("Workspace", "Espacios"):
			self.skipTest("Workspace Espacios no sincronizado")
		ws = frappe.get_doc("Workspace", "Espacios")
		roles = {r.role for r in (ws.roles or [])}
		self.assertIn(ROLE_COORDINACION, roles)
		self.assertIn("Secretaria", roles)
		self.assertIn("Tesoreria", roles)

	def test_coordinacion_puede_insertar_espacio(self) -> None:
		user = make_coordinacion_user("coord.insert@example.com")
		frappe.set_user(user)
		try:
			name = insert_espacio("Cancha Coord Insert")
			self.assertTrue(frappe.db.exists("Espacio", name))
		finally:
			frappe.set_user("Administrator")
