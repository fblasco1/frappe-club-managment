"""Tests datos críticos Socio — spec socio_alta_edicion_secretaria.md."""

from __future__ import annotations

import frappe

from club_management.members.api.socio_operaciones_desk import list_datos_criticos_faltantes_desk
from club_management.members.services.datos_criticos_socio import get_datos_criticos_faltantes_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	make_secretaria_user,
	make_socio_payload,
	minor_birthdate,
)


class TestDatosCriticosSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = make_secretaria_user("secretaria.criticos@example.com")

	def test_lista_adjuntos_y_contacto_faltantes(self) -> None:
		payload = make_socio_payload(
			dni="77001001",
			email="",
			telefono_movil="",
			calle="",
			foto_perfil="",
			dni_frente="",
			dni_dorso="",
			ficha_medica="",
		)
		payload.pop("doctype", None)
		faltantes = get_datos_criticos_faltantes_socio(payload)
		labels = {row["label"] for row in faltantes}
		self.assertIn("Email", labels)
		self.assertIn("Teléfono móvil", labels)
		self.assertIn("Calle", labels)
		self.assertIn("Ficha médica", labels)

	def test_menor_incluye_tutor_en_faltantes(self) -> None:
		payload = make_socio_payload(
			dni="77001002",
			email="menor.crit@example.com",
			fecha_nacimiento=minor_birthdate(12),
			categoria="Menor",
		)
		payload.pop("doctype", None)
		payload.pop("tipo_tutor", None)
		payload.pop("tutor", None)
		faltantes = get_datos_criticos_faltantes_socio(payload)
		labels = {row["fieldname"] for row in faltantes}
		self.assertIn("tipo_tutor", labels)
		self.assertIn("tutor", labels)

	def test_secretaria_edita_socio_sin_adjuntos_no_bloquea(self) -> None:
		socio = insert_socio(dni="77001003", email="edit.crit@example.com")
		socio.ficha_medica = ""
		socio.dni_frente = ""
		socio.dni_dorso = ""
		socio.foto_perfil = ""
		socio.telefono_movil = "1122334455"

		frappe.set_user(self._secretaria)
		try:
			socio.save(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Socio", socio.name, "telefono_movil"), "1122334455")

	def test_secretaria_edita_menor_sin_tutor_no_bloquea(self) -> None:
		tutor = insert_socio(dni="77001004", email="tutor.tmp@example.com")
		socio = insert_socio(
			dni="77001005",
			email="menor.edit@example.com",
			fecha_nacimiento=minor_birthdate(11),
			categoria="Menor",
			tipo_tutor="Socio",
			tutor=tutor.name,
		)
		socio.tipo_tutor = ""
		socio.tutor = ""
		socio.email = "menor.actualizado@example.com"

		frappe.set_user(self._secretaria)
		try:
			socio.save(ignore_permissions=True)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Socio", socio.name, "email"), "menor.actualizado@example.com")

	def test_api_list_datos_criticos_faltantes_desk(self) -> None:
		socio = insert_socio(dni="77001006", email="api.crit@example.com")
		frappe.set_user(self._secretaria)
		try:
			rows = list_datos_criticos_faltantes_desk(socio=socio.name)
		finally:
			frappe.set_user("Administrator")
		self.assertIsInstance(rows, list)
