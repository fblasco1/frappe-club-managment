"""Tests del perfil autenticado del socio (lectura y actualización).

Spec: `club_management/specs/portal_socio_perfil.md`
"""

from __future__ import annotations

import contextlib
import importlib
from types import ModuleType
from typing import Iterator

import frappe

from club_management.members.services.user_provisioning import provision_user_for_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)


PERFIL_API_MODULE = "club_management.members.api.portal_perfil"


@contextlib.contextmanager
def as_user(user: str) -> Iterator[None]:
	previous = frappe.session.user
	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(previous)


def perfil_api() -> ModuleType:
	return importlib.import_module(PERFIL_API_MODULE)


def insert_website_user(email: str, *, roles: list[str]) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Portal",
				"enabled": 1,
				"user_type": "Website User",
				"send_welcome_email": 0,
				"roles": [{"role": role} for role in roles],
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


class TestPortalSocioPerfil(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()

		self.socio_a = insert_socio(
			dni="78220001",
			email="perfil.a@example.com",
			nombre="Ana",
			apellido="Portal",
			telefono_movil="+541111111111",
			calle="Portela",
			numero="836",
			foto_perfil="/private/files/foto_a_qa.jpg",
		)
		provision_user_for_socio(self.socio_a.name)
		self.socio_a.reload()
		frappe.db.set_value(
			"Socio",
			self.socio_a.name,
			{
				"numero_socio": 78220001,
				"categoria": "Activo",
				"estado": "Activo",
			},
			update_modified=False,
		)
		self.socio_a.reload()

		self.socio_b = insert_socio(
			dni="78220002",
			email="perfil.b@example.com",
			nombre="Bruno",
			apellido="Ajeno",
			foto_perfil="/private/files/foto_b_qa.jpg",
		)
		provision_user_for_socio(self.socio_b.name)
		self.socio_b.reload()

	def test_guest_no_puede_consultar_perfil(self) -> None:
		with as_user("Guest"):
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				perfil_api().get_perfil_socio()

	def test_usuario_sin_rol_socio_es_rechazado(self) -> None:
		user = insert_website_user("perfil.sinrol@example.com", roles=[])
		with as_user(user):
			with self.assertRaises(frappe.PermissionError):
				perfil_api().get_perfil_socio()

	def test_perfil_resuelve_datos_desde_la_sesion(self) -> None:
		with as_user(self.socio_a.user):
			result = perfil_api().get_perfil_socio()

		self.assertEqual(result["nombre"], "Ana")
		self.assertEqual(result["apellido"], "Portal")
		self.assertEqual(result["dni"], "78220001")
		self.assertEqual(result["email"], "perfil.a@example.com")
		self.assertEqual(result["numero_socio"], 78220001)
		self.assertEqual(result["calle"], "Portela")
		self.assertTrue(result["tiene_foto"])
		self.assertNotIn("name", result)
		self.assertNotIn("user", result)
		self.assertNotIn("dni_frente", result)
		self.assertNotIn("dni_dorso", result)
		self.assertNotIn("ficha_medica", result)
		self.assertNotIn("foto_perfil", result)

	def test_perfil_no_expone_datos_de_otro_socio(self) -> None:
		with as_user(self.socio_a.user):
			result = perfil_api().get_perfil_socio()

		self.assertEqual(result["dni"], "78220001")
		self.assertNotEqual(result["dni"], self.socio_b.dni)
		self.assertNotEqual(result["email"], self.socio_b.email)

	def test_cliente_no_puede_pedir_otro_socio(self) -> None:
		with as_user(self.socio_a.user):
			with self.assertRaises(TypeError):
				perfil_api().get_perfil_socio(socio=self.socio_b.name)

	def test_sin_foto_tiene_foto_falso(self) -> None:
		frappe.db.set_value(
			"Socio",
			self.socio_a.name,
			"foto_perfil",
			"",
			update_modified=False,
		)
		with as_user(self.socio_a.user):
			result = perfil_api().get_perfil_socio()
		self.assertFalse(result["tiene_foto"])

	def test_foto_propia_devuelve_ruta_interna_solo_para_proxy(self) -> None:
		with as_user(self.socio_a.user):
			path = perfil_api().get_foto_perfil_path()

		self.assertEqual(path, "/private/files/foto_a_qa.jpg")

	def test_foto_ajena_por_nombre_de_archivo_no_se_autoriza(self) -> None:
		with as_user(self.socio_a.user):
			with self.assertRaises(frappe.PermissionError):
				perfil_api().assert_foto_path_pertenece_al_socio(
					"/private/files/foto_b_qa.jpg"
				)

	def test_guest_no_puede_obtener_path_de_foto(self) -> None:
		with as_user("Guest"):
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				perfil_api().get_foto_perfil_path()

	def test_actualiza_datos_personales_propios(self) -> None:
		with as_user(self.socio_a.user):
			result = perfil_api().update_perfil_socio(
				{
					"telefono_movil": "+5491112345678",
					"calle": "Av. San Juan",
					"numero": "3500",
					"localidad_barrio": "Boedo",
					"nombre": "Ana María",
				}
			)

		self.assertEqual(result["telefono_movil"], "+5491112345678")
		self.assertEqual(result["calle"], "Av. San Juan")
		self.assertEqual(result["numero"], "3500")
		self.assertEqual(result["localidad_barrio"], "Boedo")
		self.assertEqual(result["nombre"], "Ana María")
		self.socio_a.reload()
		self.assertEqual(self.socio_a.telefono_movil, "+5491112345678")
		self.assertEqual(self.socio_a.calle, "Av. San Juan")
		self.assertEqual(self.socio_a.dni, "78220001")
		self.assertEqual(self.socio_a.email, "perfil.a@example.com")
		self.assertEqual(self.socio_a.estado, "Activo")

	def test_campos_bloqueados_rechazan_el_update(self) -> None:
		estado_antes = self.socio_a.estado
		with as_user(self.socio_a.user):
			with self.assertRaises(frappe.ValidationError):
				perfil_api().update_perfil_socio({"dni": "99999999", "calle": "Nueva"})
		self.socio_a.reload()
		self.assertEqual(self.socio_a.dni, "78220001")
		self.assertEqual(self.socio_a.calle, "Portela")
		self.assertEqual(self.socio_a.estado, estado_antes)

	def test_email_bloqueado_en_update(self) -> None:
		with as_user(self.socio_a.user):
			with self.assertRaises(frappe.ValidationError):
				perfil_api().update_perfil_socio({"email": "otro@example.com"})
		self.socio_a.reload()
		self.assertEqual(self.socio_a.email, "perfil.a@example.com")

	def test_update_no_acepta_selector_de_otro_socio(self) -> None:
		calle_b = self.socio_b.calle
		with as_user(self.socio_a.user):
			with self.assertRaises(TypeError):
				perfil_api().update_perfil_socio(
					{"calle": "Hack"}, socio=self.socio_b.name
				)
		self.socio_b.reload()
		self.assertEqual(self.socio_b.calle, calle_b)

	def test_guest_no_puede_actualizar_perfil(self) -> None:
		with as_user("Guest"):
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				perfil_api().update_perfil_socio({"calle": "X"})

	def test_update_de_a_no_modifica_a_b(self) -> None:
		calle_b = self.socio_b.calle
		with as_user(self.socio_a.user):
			perfil_api().update_perfil_socio({"calle": "Solo A"})
		self.socio_b.reload()
		self.assertEqual(self.socio_b.calle, calle_b)
		self.socio_a.reload()
		self.assertEqual(self.socio_a.calle, "Solo A")
