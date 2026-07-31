"""Tests alta y edición manual de Socio por Secretaría (spec socio_alta_edicion_secretaria.md)."""

from __future__ import annotations

import datetime
import json
from unittest.mock import patch

import frappe

from club_management.members.api.socio_operaciones_desk import crear_socio_desk as crear_socio_desk_api
from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible
from club_management.members.services.socio_alta_secretaria import (
	crear_socio_desk,
	sugerir_categoria_por_fecha_nacimiento,
)
from club_management.members.services.suscripciones_socio import suscripciones_habilitadas
from club_management.members.test_helpers import (
	DUMMY_DNI_DORSO,
	DUMMY_DNI_FRENTE,
	DUMMY_FICHA_MEDICA,
	DUMMY_FOTO_PERFIL,
	MembersTestCase,
	adult_birthdate,
	insert_grupo_familiar_solo_socio,
	insert_socio,
	insert_tutor_no_socio,
	make_secretaria_user,
	make_socio_payload,
	minor_birthdate,
)


def _datos_alta_adulto(**overrides) -> dict:
	defaults = {"dni": "30998877", "email": "alta.manual@example.com"}
	defaults.update(overrides)
	payload = make_socio_payload(**defaults)
	payload.pop("doctype", None)
	return payload


class TestSocioAltaSecretaria(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = make_secretaria_user("secretaria.alta@example.com")

	def _customer_for_socio(self, socio_name: str) -> str | None:
		for field in ("socio", "custom_socio"):
			if frappe.get_meta("Customer").has_field(field):
				return frappe.db.get_value("Customer", {field: socio_name}, "name")
		return None

	def test_secretaria_crea_socio_adulto_pendiente_pago(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(_datos_alta_adulto())
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.estado, "Pendiente de Pago")
		self.assertFalse(socio.fecha_alta)
		self.assertEqual(socio.categoria, "Activo")

		if erpnext_cobranza_disponible():
			self.assertTrue(self._customer_for_socio(socio_name))

	def test_crear_socio_dispara_sync_suscripcion_cuota(self) -> None:
		if not suscripciones_habilitadas():
			self.skipTest("ERPNext Subscriptions no instalado")

		frappe.set_user(self._secretaria)
		try:
			with patch(
				"club_management.members.services.socio_alta_secretaria.sync_suscripcion_cuota_al_validar_socio"
			) as mocked_sync:
				socio_name = crear_socio_desk(_datos_alta_adulto(dni="30997766", email="sync@example.com"))
		finally:
			frappe.set_user("Administrator")

		mocked_sync.assert_called_once_with(socio_name)

	def test_activar_al_guardar_deja_socio_activo(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(dni="30996655", email="activo@example.com"),
				activar_al_guardar=True,
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(socio.fecha_alta, datetime.date.today())

	def test_dni_duplicado_falla(self) -> None:
		insert_socio(dni="30123456", email="existente@example.com")
		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				crear_socio_desk(_datos_alta_adulto(dni="30123456", email="otro@example.com"))
		finally:
			frappe.set_user("Administrator")

	def test_menor_sin_tutor_se_crea(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(
					dni="55112233",
					email="menor@example.com",
					fecha_nacimiento=minor_birthdate(12),
					categoria="Menor",
				)
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.categoria, "Menor")
		self.assertFalse(socio.tipo_tutor)
		self.assertFalse(socio.tutor)

	def test_menor_con_tutor_incompleto_falla(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				crear_socio_desk(
					_datos_alta_adulto(
						dni="55112234",
						email="menor.incompleto@example.com",
						fecha_nacimiento=minor_birthdate(12),
						categoria="Menor",
						tipo_tutor="Tutor No Socio",
					)
				)
		finally:
			frappe.set_user("Administrator")

	def test_menor_con_tutor_socio_sin_grupo_familiar_se_crea(self) -> None:
		tutor = insert_socio(dni="30110001", email="tutor.sin.grupo@example.com")

		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(
					dni="55113399",
					email="hijo.sin.grupo@example.com",
					fecha_nacimiento=minor_birthdate(10),
					categoria="Menor",
					tipo_tutor="Socio",
					tutor=tutor.name,
				)
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.categoria, "Menor")
		self.assertEqual(socio.tutor, tutor.name)
		self.assertFalse(socio.grupo_familiar)

	def test_menor_con_tutor_socio_se_crea(self) -> None:
		tutor = insert_socio(dni="30110000", email="tutor@example.com")
		grupo = insert_grupo_familiar_solo_socio(tutor.name)

		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(
					dni="55113344",
					email="hijo@example.com",
					fecha_nacimiento=minor_birthdate(10),
					categoria="Menor",
					tipo_tutor="Socio",
					tutor=tutor.name,
					grupo_familiar=grupo.name,
				)
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.categoria, "Menor")
		self.assertEqual(socio.tutor, tutor.name)
		self.assertEqual(socio.grupo_familiar, grupo.name)

	def test_menor_con_tutor_no_socio_se_crea(self) -> None:
		from club_management.members.test_helpers import insert_grupo_familiar_solo_tutor

		tutor = insert_tutor_no_socio(dni="20112233", email="tns@example.com")
		grupo = insert_grupo_familiar_solo_tutor(tutor.name)

		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(
					dni="55114455",
					email="hijo2@example.com",
					fecha_nacimiento=minor_birthdate(9),
					categoria="Menor",
					tipo_tutor="Tutor No Socio",
					tutor=tutor.name,
					grupo_familiar=grupo.name,
				)
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.tipo_tutor, "Tutor No Socio")
		self.assertEqual(socio.tutor, tutor.name)

	def test_usuario_sin_rol_no_puede_crear(self) -> None:
		socio = insert_socio(dni="30887766", email="socio.perm@example.com")
		email = f"socio_perm_{socio.dni}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)

		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				crear_socio_desk(_datos_alta_adulto(dni="30995544", email="nuevo@example.com"))
		finally:
			frappe.set_user("Administrator")

	def test_alta_sin_adjuntos_opcionales(self) -> None:
		payload = _datos_alta_adulto(dni="30993322", email="sin.adj@example.com")
		for campo in ("foto_perfil", "dni_frente", "dni_dorso", "ficha_medica"):
			payload.pop(campo, None)

		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(payload)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(frappe.db.exists("Socio", socio_name))

	def test_sugerir_categoria_menor(self) -> None:
		self.assertEqual(
			sugerir_categoria_por_fecha_nacimiento(minor_birthdate(12)),
			"Menor",
		)
		self.assertEqual(
			sugerir_categoria_por_fecha_nacimiento(adult_birthdate(30)),
			"Activo",
		)

	def test_activar_e_inscribir_en_un_paso(self) -> None:
		if frappe.db.exists("Actividad", "Zumba Alta Guiada"):
			actividad = "Zumba Alta Guiada"
		else:
			actividad = frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": "Zumba Alta Guiada",
					"habilitada": 1,
					"usa_grupos": 0,
				}
			).insert(ignore_permissions=True).name

		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(dni="30992211", email="alta.insc@example.com"),
				activar_al_guardar=True,
				selecciones_inscripcion=[{"actividad": actividad}],
			)
		finally:
			frappe.set_user("Administrator")

		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(
			frappe.db.count(
				"Inscripcion Actividad",
				{"socio": socio_name, "actividad": actividad, "estado": "Activa"},
			),
			1,
		)

	def test_omitir_pago_deja_pendiente_inscripcion(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(dni="30991100", email="omitir@example.com"),
				omitir_pago_al_guardar=True,
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(
			frappe.db.get_value("Socio", socio_name, "estado"),
			"Pendiente de Inscripción",
		)

	def test_alta_con_numero_socio_manual(self) -> None:
		frappe.set_user(self._secretaria)
		try:
			socio_name = crear_socio_desk(
				_datos_alta_adulto(
					dni="30990088",
					email="numero.manual@example.com",
					numero_socio=1500,
				)
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(socio_name, "1500")
		socio = frappe.get_doc("Socio", socio_name)
		self.assertEqual(int(socio.numero_socio), 1500)

	def test_numero_socio_duplicado_falla(self) -> None:
		insert_socio(dni="30880011", email="existente.num@example.com", numero_socio=1500)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				crear_socio_desk(
					_datos_alta_adulto(
						dni="30880022",
						email="duplicado.num@example.com",
						numero_socio=1500,
					)
				)
		finally:
			frappe.set_user("Administrator")

	def test_api_crear_socio_desk_requiere_secretaria(self) -> None:
		datos = _datos_alta_adulto(dni="30994433", email="api@example.com")
		datos["fecha_nacimiento"] = str(datos["fecha_nacimiento"])
		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				crear_socio_desk_api(
					datos=json.dumps(datos),
					activar_al_guardar=0,
				)
		finally:
			frappe.set_user("Administrator")


class TestSocioEdicionSecretaria(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = make_secretaria_user("secretaria.edit@example.com")

	def test_edicion_datos_personales_no_cambia_estado_ni_fecha_alta(self) -> None:
		from club_management.members.services.socio_transitions import cambiar_estado

		socio = insert_socio(dni="30776655", email="edit@example.com")
		cambiar_estado(socio.name, "Pendiente de Pago", motivo="Alta manual")
		socio.reload()
		estado_previo = socio.estado
		fecha_previa = socio.fecha_alta

		frappe.set_user(self._secretaria)
		try:
			doc = frappe.get_doc("Socio", socio.name)
			doc.nombre = "María"
			doc.apellido = "Gómez"
			doc.telefono_fijo = "01144443333"
			doc.telefono_movil = "+5411999888777"
			doc.calle = "Nueva Calle 456"
			doc.categoria = "Adherente"
			doc.save()
		finally:
			frappe.set_user("Administrator")

		doc.reload()
		self.assertEqual(doc.nombre, "María")
		self.assertEqual(doc.apellido, "Gómez")
		self.assertEqual(doc.telefono_fijo, "01144443333")
		self.assertEqual(doc.telefono_movil, "+5411999888777")
		self.assertEqual(doc.calle, "Nueva Calle 456")
		self.assertEqual(doc.categoria, "Adherente")
		self.assertEqual(doc.estado, estado_previo)
		self.assertEqual(doc.fecha_alta, fecha_previa)

	def test_edicion_directa_estado_falla(self) -> None:
		socio = insert_socio(dni="30665544", email="estado@example.com")
		frappe.set_user(self._secretaria)
		try:
			doc = frappe.get_doc("Socio", socio.name)
			doc.estado = "Activo"
			with self.assertRaises(frappe.ValidationError):
				doc.save()
		finally:
			frappe.set_user("Administrator")
