"""Tests BL-6 del portal autenticado de inscripción a actividades."""

from __future__ import annotations

import contextlib
import importlib
from types import ModuleType
from typing import Iterator

import frappe

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
)
from club_management.members.services.user_provisioning import provision_user_for_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
)


PORTAL_API_MODULE = "club_management.activities.api.portal_socio"


@contextlib.contextmanager
def as_user(user: str) -> Iterator[None]:
	previous = frappe.session.user
	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(previous)


def portal_api() -> ModuleType:
	"""Carga tarde el módulo para que la suite descubra todos los tests rojos."""
	return importlib.import_module(PORTAL_API_MODULE)


def insert_actividad(
	titulo: str,
	*,
	tipo_portal: str = "plana",
	usa_grupos: bool = False,
) -> frappe.model.document.Document:
	doc = frappe.get_doc(
		{
			"doctype": "Actividad",
			"titulo": titulo,
			"habilitada": 1,
			"usa_grupos": int(usa_grupos),
			"tipo_inscripcion_portal": tipo_portal,
			"orden": 999,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def insert_grupo(
	actividad: str,
	titulo: str,
	*,
	portal_socio_elige: bool,
	habilitada: bool = True,
) -> frappe.model.document.Document:
	return frappe.get_doc(
		{
			"doctype": "Grupo Actividad",
			"name": f"{actividad} / {titulo}",
			"actividad": actividad,
			"titulo": titulo,
			"habilitada": int(habilitada),
			"portal_socio_elige": int(portal_socio_elige),
			"orden": 999,
		}
	).insert(ignore_permissions=True)


def insert_website_user(email: str, *, roles: list[str]) -> str:
	return frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Portal",
			"enabled": 1,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert(ignore_permissions=True).name


class TestPortalSocioMetadata(MembersTestCase):
	def test_actividad_declara_tipo_inscripcion_portal(self) -> None:
		field = frappe.get_meta("Actividad").get_field("tipo_inscripcion_portal")

		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Select")
		self.assertIn("plana", field.options)
		self.assertIn("deporte", field.options)
		self.assertIn("variante_grupo", field.options)

	def test_grupo_declara_si_el_socio_puede_elegirlo(self) -> None:
		field = frappe.get_meta("Grupo Actividad").get_field("portal_socio_elige")

		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Check")
		self.assertEqual(field.default, "0")


class TestPortalSocioInscripcionIsolation(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()

		self.socio_a = insert_socio(dni="78110001", email="portal.a@example.com")
		provision_user_for_socio(self.socio_a.name)
		self.socio_a.reload()

		self.socio_b = insert_socio(dni="78110002", email="portal.b@example.com")
		provision_user_for_socio(self.socio_b.name)
		self.socio_b.reload()

		self.actividad = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": "Portal BL6 Aislamiento",
				"habilitada": 1,
				"usa_grupos": 0,
				"orden": 999,
			}
		).insert(ignore_permissions=True)
		self.inscripcion_a = self._insert_inscripcion(self.socio_a.name)
		self.inscripcion_b = self._insert_inscripcion(self.socio_b.name)

	def _insert_inscripcion(self, socio: str) -> frappe.model.document.Document:
		return frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio,
				"actividad": self.actividad.name,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

	def test_socio_lista_solo_sus_inscripciones(self) -> None:
		with as_user(self.socio_a.user):
			names = frappe.get_list("Inscripcion Actividad", pluck="name")

		self.assertIn(self.inscripcion_a.name, names)
		self.assertNotIn(self.inscripcion_b.name, names)

	def test_socio_no_puede_abrir_inscripcion_ajena(self) -> None:
		with as_user(self.socio_a.user):
			self.assertFalse(
				frappe.has_permission(
					"Inscripcion Actividad",
					"read",
					doc=self.inscripcion_b.name,
					user=self.socio_a.user,
				)
			)
			with self.assertRaises(frappe.PermissionError):
				frappe.has_permission(
					"Inscripcion Actividad",
					"read",
					doc=self.inscripcion_b.name,
					user=self.socio_a.user,
					throw=True,
				)

	def test_api_lista_solo_inscripciones_propias(self) -> None:
		with as_user(self.socio_a.user):
			rows = portal_api().list_inscripciones_propias()

		names = {row["name"] for row in rows}
		self.assertIn(self.inscripcion_a.name, names)
		self.assertNotIn(self.inscripcion_b.name, names)
		self.assertTrue(all("socio" not in row for row in rows))

	def test_query_conditions_filtran_por_sesion_en_postgres(self) -> None:
		from club_management.activities.permissions import (
			inscripcion_actividad_query_conditions,
		)

		with as_user(self.socio_a.user):
			sql = inscripcion_actividad_query_conditions()

		self.assertIn('"tabInscripcion Actividad"."socio"', sql)
		self.assertIn('"tabSocio"', sql)
		self.assertNotIn("`", sql)
		self.assertIn(self.socio_a.user, sql)
		self.assertNotIn(self.socio_b.user, sql)

	def test_insert_rechaza_socio_ajeno_aunque_venga_en_el_body(self) -> None:
		with as_user(self.socio_a.user):
			with self.assertRaises(frappe.PermissionError):
				frappe.get_doc(
					{
						"doctype": "Inscripcion Actividad",
						"socio": self.socio_b.name,
						"actividad": self.actividad.name,
						"estado": "Activa",
					}
				).insert(ignore_permissions=True)

		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio_b.name}),
			1,
		)


class TestPortalSocioInscripcionApi(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()
		self.socio = insert_socio(dni="78110003", email="portal.api@example.com")
		provision_user_for_socio(self.socio.name)
		self.socio.reload()
		frappe.db.set_value(
			"Socio",
			self.socio.name,
			"estado",
			ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
			update_modified=False,
		)

	def test_guest_no_puede_consultar_contexto(self) -> None:
		with as_user("Guest"):
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				portal_api().get_contexto_socio()

	def test_guest_no_puede_consultar_catalogo_ni_confirmar(self) -> None:
		with as_user("Guest"):
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				portal_api().get_catalogo_inscripcion()
			with self.assertRaises((frappe.AuthenticationError, frappe.PermissionError)):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[{"actividad": "cualquier-actividad"}]
				)

	def test_contexto_resuelve_socio_desde_la_sesion(self) -> None:
		with as_user(self.socio.user):
			result = portal_api().get_contexto_socio()

		self.assertTrue(result["elegible"])
		self.assertEqual(result["estado"], ESTADO_SOCIO_PENDIENTE_INSCRIPCION)
		self.assertNotIn("socio", result)

	def test_usuario_sin_rol_socio_es_rechazado(self) -> None:
		user = insert_website_user("portal.sinrol@example.com", roles=[])

		with as_user(user):
			with self.assertRaises(frappe.PermissionError):
				portal_api().get_contexto_socio()

	def test_rol_socio_sin_vinculo_es_rechazado(self) -> None:
		user = insert_website_user("portal.sinvinculo@example.com", roles=["Socio"])

		with as_user(user):
			with self.assertRaises(frappe.PermissionError):
				portal_api().get_contexto_socio()

	def test_seleccion_vacia_no_activa_socio(self) -> None:
		with as_user(self.socio.user):
			with self.assertRaises(frappe.ValidationError):
				portal_api().confirmar_inscripcion_actividades(selecciones=[])

		self.assertEqual(
			frappe.db.get_value("Socio", self.socio.name, "estado"),
			ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
		)
		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio.name}),
			0,
		)

	def test_replay_no_duplica_inscripcion(self) -> None:
		actividad = insert_actividad("Portal BL6 Replay")
		selecciones = [{"actividad": actividad.name}]

		with as_user(self.socio.user):
			first = portal_api().confirmar_inscripcion_actividades(selecciones=selecciones)
			second = portal_api().confirmar_inscripcion_actividades(selecciones=selecciones)

		self.assertEqual(first["status"], "ok")
		self.assertEqual(second["status"], "ok")
		self.assertNotIn("socio", first)
		self.assertEqual(
			frappe.db.count(
				"Inscripcion Actividad",
				{
					"socio": self.socio.name,
					"actividad": actividad.name,
					"estado": "Activa",
				},
			),
			1,
		)

	def test_cliente_no_puede_indicar_otro_socio(self) -> None:
		with as_user(self.socio.user):
			with self.assertRaises(TypeError):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[{"actividad": "cualquier-actividad"}],
					socio="otro-socio",
				)

	def test_socio_no_elegible_no_puede_crear_inscripcion(self) -> None:
		actividad = insert_actividad("Portal BL6 No Elegible")
		frappe.db.set_value(
			"Socio",
			self.socio.name,
			"estado",
			"Moroso",
			update_modified=False,
		)

		with as_user(self.socio.user):
			with self.assertRaises(frappe.ValidationError):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[{"actividad": actividad.name}]
				)

		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio.name}),
			0,
		)

	def test_catalogo_incluye_tipo_y_solo_grupos_seleccionables(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Variante",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		permitido = insert_grupo(
			actividad.name,
			"Una clase",
			portal_socio_elige=True,
		)
		insert_grupo(
			actividad.name,
			"Tira interna",
			portal_socio_elige=False,
		)

		with as_user(self.socio.user):
			catalogo = portal_api().get_catalogo_inscripcion()

		row = next(item for item in catalogo if item["value"] == actividad.name)
		self.assertEqual(row["tipo_inscripcion_portal"], "variante_grupo")
		self.assertEqual(
			row["grupos"],
			[{"value": permitido.name, "label": permitido.titulo}],
		)
		self.assertNotIn("equipos", row)

	def test_deporte_permite_inscripcion_sin_tira_ni_equipo(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Deporte",
			tipo_portal="deporte",
			usa_grupos=True,
		)

		with as_user(self.socio.user):
			result = portal_api().confirmar_inscripcion_actividades(
				selecciones=[{"actividad": actividad.name}]
			)

		self.assertEqual(result["status"], "ok")
		inscripcion = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": self.socio.name, "actividad": actividad.name},
			["grupo_actividad", "equipo_actividad"],
			as_dict=True,
		)
		self.assertIsNotNone(inscripcion)
		self.assertFalse(inscripcion.grupo_actividad)
		self.assertFalse(inscripcion.equipo_actividad)

	def test_variante_requiere_grupo_marcado_para_portal(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Grupo",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		permitido = insert_grupo(
			actividad.name,
			"Dos clases",
			portal_socio_elige=True,
		)

		with as_user(self.socio.user):
			result = portal_api().confirmar_inscripcion_actividades(
				selecciones=[
					{
						"actividad": actividad.name,
						"grupo_actividad": permitido.name,
					}
				]
			)

		self.assertEqual(result["status"], "ok")
		self.assertTrue(
			frappe.db.exists(
				"Inscripcion Actividad",
				{
					"socio": self.socio.name,
					"actividad": actividad.name,
					"grupo_actividad": permitido.name,
				},
			)
		)

	def test_variante_rechaza_grupo_interno_sin_efectos(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Grupo Interno",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		interno = insert_grupo(
			actividad.name,
			"Tira competitiva",
			portal_socio_elige=False,
		)

		with as_user(self.socio.user):
			with self.assertRaises(frappe.ValidationError):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[
						{
							"actividad": actividad.name,
							"grupo_actividad": interno.name,
						}
					]
				)

		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio.name}),
			0,
		)
		self.assertEqual(
			frappe.db.get_value("Socio", self.socio.name, "estado"),
			ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
		)

	def test_variante_rechaza_grupo_deshabilitado(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Grupo Deshabilitado",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		grupo = insert_grupo(
			actividad.name,
			"Variante antigua",
			portal_socio_elige=True,
			habilitada=False,
		)

		with as_user(self.socio.user):
			with self.assertRaises(frappe.ValidationError):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[
						{
							"actividad": actividad.name,
							"grupo_actividad": grupo.name,
						}
					]
				)

		self.assertFalse(
			frappe.db.exists(
				"Inscripcion Actividad",
				{"socio": self.socio.name, "grupo_actividad": grupo.name},
			)
		)

	def test_variante_rechaza_grupo_de_otra_actividad(self) -> None:
		actividad = insert_actividad(
			"Portal BL6 Grupo Cruzado",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		otra = insert_actividad(
			"Portal BL6 Otra Actividad",
			tipo_portal="variante_grupo",
			usa_grupos=True,
		)
		grupo_ajeno = insert_grupo(
			otra.name,
			"Grupo ajeno",
			portal_socio_elige=True,
		)

		with as_user(self.socio.user):
			with self.assertRaises(frappe.ValidationError):
				portal_api().confirmar_inscripcion_actividades(
					selecciones=[
						{
							"actividad": actividad.name,
							"grupo_actividad": grupo_ajeno.name,
						}
					]
				)

		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio.name}),
			0,
		)
