"""Tests rol Tesoreria y permisos."""

from __future__ import annotations

import frappe

from club_management.finance.permissions import (
	ROLE_TESORERIA,
	ensure_carga_rapida_access,
	ensure_role_tesoreria_exists,
	ensure_tesoreria_access,
)
from club_management.finance.services.flujo_fondos import calcular_proyeccion_flujo_fondos
from club_management.members.permissions_app import has_app_permission
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_secretaria_exists,
	make_secretaria_user,
)


def ensure_role_tesoreria_for_tests() -> None:
	ensure_role_tesoreria_exists()


def make_tesoreria_user(email: str = "tesoreria.test@example.com") -> str:
	ensure_role_tesoreria_for_tests()
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if ROLE_TESORERIA not in {r.role for r in user.roles}:
			user.append("roles", {"role": ROLE_TESORERIA})
			user.save(ignore_permissions=True)
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Tesoreria",
			"send_welcome_email": 0,
			"roles": [{"role": ROLE_TESORERIA}],
		}
	).insert(ignore_permissions=True)
	return email


class TestRolTesoreria(MembersTestCase):
	def test_ensure_role_tesoreria_crea_rol_con_desk(self) -> None:
		if frappe.db.exists("Role", ROLE_TESORERIA):
			frappe.delete_doc("Role", ROLE_TESORERIA, force=1)
		ensure_role_tesoreria_exists()
		self.assertTrue(frappe.db.exists("Role", ROLE_TESORERIA))
		self.assertEqual(frappe.db.get_value("Role", ROLE_TESORERIA, "desk_access"), 1)

	def test_tesoreria_accede_proyeccion(self) -> None:
		if not frappe.db.exists("DocType", "Purchase Invoice"):
			self.skipTest("ERPNext no instalado")
		try:
			from club_management.setup.icdpe_company import resolve_icdpe_company

			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")

		user = make_tesoreria_user("tesoreria.flujo@example.com")
		frappe.set_user(user)
		try:
			result = calcular_proyeccion_flujo_fondos(ventana_dias=5)
		finally:
			frappe.set_user("Administrator")
		self.assertIn("saldo_caja_bancos", result)
		self.assertIn("liquidez_alcanza", result)

	def test_secretaria_no_accede_proyeccion(self) -> None:
		ensure_role_secretaria_exists()
		user = make_secretaria_user("secretaria.sin.tesoreria@example.com")
		# Asegurar que no tenga Tesoreria
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role != ROLE_TESORERIA]
		doc.save(ignore_permissions=True)

		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				ensure_tesoreria_access()
			with self.assertRaises(frappe.PermissionError):
				calcular_proyeccion_flujo_fondos()
		finally:
			frappe.set_user("Administrator")

	def test_tesoreria_no_carga_rapida(self) -> None:
		user = make_tesoreria_user("tesoreria.sin.carga@example.com")
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role != "Secretaria"]
		doc.save(ignore_permissions=True)

		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				ensure_carga_rapida_access()
		finally:
			frappe.set_user("Administrator")

	def test_workspace_tesoreria_sin_secretaria(self) -> None:
		from club_management.patches.v1_0.sync_tesoreria_workspace import execute as sync_ws

		sync_ws()
		if not frappe.db.exists("Workspace", "Tesorería"):
			self.skipTest("Workspace Tesorería no sincronizado")
		ws = frappe.get_doc("Workspace", "Tesorería")
		roles = {r.role for r in (ws.roles or [])}
		self.assertIn(ROLE_TESORERIA, roles)
		self.assertIn("System Manager", roles)
		self.assertNotIn("Secretaria", roles)

	def test_has_app_permission_tesoreria(self) -> None:
		user = make_tesoreria_user("tesoreria.app@example.com")
		frappe.set_user(user)
		try:
			self.assertTrue(has_app_permission())
		finally:
			frappe.set_user("Administrator")
