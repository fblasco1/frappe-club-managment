"""Tests de Workflow, auditoría y validación — `Solicitud Asociacion` (Sprint 1).

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commits 3–4).
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from club_management.members.services.validar_solicitud import (
	MSG_DNI_YA_SOCIO,
	MSG_DNI_YA_TNS,
	MSG_EMAIL_ADULTO_TOMADO,
	MSG_EMAIL_MENOR_TOMADO,
	MSG_TUTOR_MENOR_EDAD,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	adult_birthdate,
	apply_workflow_solicitar_correccion,
	ensure_role_socio_exists,
	insert_grupo_familiar_solo_socio,
	insert_grupo_familiar_solo_tutor,
	insert_socio,
	insert_solicitud_asociacion,
	insert_tutor_no_socio,
	make_secretaria_user,
	make_solicitud_menor_payload,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_REENVIAR,
	ACTION_SOLICITAR_CORRECCION,
	ACTION_VALIDAR,
	DOCUMENT_TYPE,
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
	STATE_VALIDADA,
	WORKFLOW_ACTIONS,
	WORKFLOW_NAME,
	WORKFLOW_STATES,
	ensure_solicitud_asociacion_workflow,
)

DOCTYPE = DOCUMENT_TYPE


class TestSolicitudAsociacionWorkflowFixture(MembersTestCase):
	"""Fixture del Workflow tras migrate / ensure."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def test_workflow_activo_para_solicitud_asociacion(self) -> None:
		self.assertTrue(frappe.db.exists("Workflow", WORKFLOW_NAME))
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		self.assertEqual(wf.document_type, DOCTYPE)
		self.assertEqual(wf.workflow_state_field, "workflow_state")
		self.assertEqual(wf.is_active, 1)

	def test_workflow_declara_estados_y_acciones(self) -> None:
		wf = frappe.get_doc("Workflow", WORKFLOW_NAME)
		states = {row.state for row in wf.states}
		self.assertEqual(states, set(WORKFLOW_STATES))

		actions = {row.action for row in wf.transitions}
		self.assertEqual(actions, set(WORKFLOW_ACTIONS))


class TestSolicitudAsociacionWorkflowTransiciones(MembersTestCase):
	"""Transiciones Desk vía `apply_workflow`."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def setUp(self) -> None:
		super().setUp()
		self.secretaria = make_secretaria_user()
		frappe.set_user(self.secretaria)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		super().tearDown()

	def test_solicitar_correccion_pasa_a_requiere_correccion(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_REQUIERE_CORRECCION)

	def test_reenviar_vuelve_a_pendiente(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		apply_workflow(doc, ACTION_REENVIAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)

	def test_validar_pasa_a_validada(self) -> None:
		sol = insert_solicitud_asociacion(dni="30999001", email="validar.wf@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		self.assertTrue(doc.socio_generado)

	def test_solicitar_correccion_con_observaciones_pasa_a_requiere_correccion(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow_solicitar_correccion(doc, "DNI borroso")
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_REQUIERE_CORRECCION)


class TestSolicitudAsociacionWorkflowAuditoria(MembersTestCase):
	"""Campos de auditoría seteados en `before_save`."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def setUp(self) -> None:
		super().setUp()
		self.secretaria = make_secretaria_user()
		frappe.set_user(self.secretaria)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		super().tearDown()

	def test_solicitar_correccion_audita_usuario_y_timestamp(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		doc.reload()
		self.assertEqual(doc.correccion_solicitada_por, self.secretaria)
		self.assertIsNotNone(doc.correccion_solicitada_en)

	def test_validar_audita_usuario_y_timestamp(self) -> None:
		sol = insert_solicitud_asociacion(dni="30999002", email="audita.validar@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		self.assertEqual(doc.validado_por, self.secretaria)
		self.assertIsNotNone(doc.validado_en)

	def test_reenviar_no_borra_auditoria_de_correccion(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		doc.reload()
		correccion_por = doc.correccion_solicitada_por
		correccion_en = doc.correccion_solicitada_en

		apply_workflow(doc, ACTION_REENVIAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)
		self.assertEqual(doc.correccion_solicitada_por, correccion_por)
		self.assertEqual(doc.correccion_solicitada_en, correccion_en)

	def test_save_sin_cambio_de_estado_no_sobrescribe_validado(self) -> None:
		sol = insert_solicitud_asociacion(dni="30999003", email="save.validado@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		validado_por = doc.validado_por
		validado_en = doc.validado_en

		doc.observaciones_secretaria = "Nota interna"
		doc.save()
		doc.reload()
		self.assertEqual(doc.validado_por, validado_por)
		self.assertEqual(doc.validado_en, validado_en)


class TestValidarSolicitud(MembersTestCase):
	"""Commit 4 — `validar_solicitud` y `ensure_grupo_for_socio`."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def setUp(self) -> None:
		super().setUp()
		self.secretaria = make_secretaria_user()
		frappe.set_user(self.secretaria)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		super().tearDown()

	def _validar(self, doc):
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		) as mock_email:
			apply_workflow(doc, ACTION_VALIDAR)
			return mock_email

	def test_validar_adulto_crea_user_socio_y_grupo(self) -> None:
		sol = insert_solicitud_asociacion(dni="40111222", email="adulto.validar@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		mock_email = self._validar(doc)
		doc.reload()

		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		self.assertTrue(doc.socio_generado)
		self.assertTrue(doc.user_generado)
		self.assertTrue(doc.grupo_familiar_generado)

		socio = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio.estado, "Pendiente de Pago")
		self.assertEqual(socio.dni, "40111222")
		self.assertEqual(socio.solicitud_origen, sol.name)
		self.assertEqual(socio.grupo_familiar, doc.grupo_familiar_generado)
		self.assertTrue(frappe.db.exists("User", doc.user_generado))
		mock_email.assert_called_once_with(sol.name, "adulto.validar@example.com")

	def test_validar_adulto_email_tomado_bloquea(self) -> None:
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "tomado@example.com",
				"first_name": "Otro",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		sol = insert_solicitud_asociacion(dni="40111333", email="tomado@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with self.assertRaises(ValidationError) as ctx:
			self._validar(doc)
		self.assertIn(MSG_EMAIL_ADULTO_TOMADO, str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)
		self.assertFalse(doc.socio_generado)

	def test_validar_dni_ya_socio_bloquea(self) -> None:
		insert_socio(dni="40111444", email="existente@example.com")
		sol = insert_solicitud_asociacion(dni="40111444", email="nuevo@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with self.assertRaises(ValidationError) as ctx:
			self._validar(doc)
		self.assertIn(MSG_DNI_YA_SOCIO, str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)

	def test_validar_dni_ya_tns_bloquea_adulto(self) -> None:
		insert_tutor_no_socio(dni="40111555", email="tutor@example.com")
		sol = insert_solicitud_asociacion(dni="40111555", email="aspira@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with self.assertRaises(ValidationError) as ctx:
			self._validar(doc)
		self.assertIn(MSG_DNI_YA_TNS, str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)

	def test_validar_menor_tutor_socio_email_compartido(self) -> None:
		tutor = insert_socio(dni="20111222", email="familia@example.com")
		grupo = insert_grupo_familiar_solo_socio(tutor.name)
		ensure_role_socio_exists()
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "familia@example.com",
				"username": "20111222",
				"first_name": "Tutor",
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)

		sol = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222111",
				email="familia@example.com",
				dni_tutor="20111222",
				email_tutor="familia@example.com",
			)
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(DOCTYPE, sol.name)
		mock_email = self._validar(doc)
		doc.reload()

		self.assertEqual(doc.grupo_familiar_generado, grupo.name)
		self.assertFalse(doc.user_generado)
		socio_menor = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio_menor.categoria, "Menor")
		self.assertFalse(socio_menor.user)
		mock_email.assert_called_once_with(sol.name, "familia@example.com")

	def test_validar_menor_tutor_socio_email_unico(self) -> None:
		tutor = insert_socio(dni="20111333", email="papa@example.com")
		insert_grupo_familiar_solo_socio(tutor.name)
		sol = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222222",
				email="ana@example.com",
				dni_tutor="20111333",
				email_tutor="papa@example.com",
			)
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(DOCTYPE, sol.name)
		self._validar(doc)
		doc.reload()
		self.assertTrue(doc.user_generado)
		self.assertEqual(frappe.db.get_value("User", doc.user_generado, "name"), "ana@example.com")

	def test_validar_menor_email_tomado_bloquea(self) -> None:
		frappe.get_doc(
			{
				"doctype": "User",
				"email": "ana@example.com",
				"first_name": "Otra",
				"send_welcome_email": 0,
			}
		).insert(ignore_permissions=True)
		tutor = insert_socio(dni="20111444", email="papa@example.com")
		insert_grupo_familiar_solo_socio(tutor.name)
		sol = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222333",
				email="ana@example.com",
				dni_tutor="20111444",
				email_tutor="papa@example.com",
			)
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with self.assertRaises(ValidationError) as ctx:
			self._validar(doc)
		self.assertIn(MSG_EMAIL_MENOR_TOMADO, str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)

	def test_validar_menor_tutor_nuevo_tns(self) -> None:
		sol = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222444",
				email="hijo@example.com",
				dni_tutor="20111555",
				email_tutor="padre.nuevo@example.com",
			)
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(DOCTYPE, sol.name)
		self._validar(doc)
		doc.reload()
		self.assertTrue(frappe.db.exists("Tutor No Socio", {"dni": "20111555"}))
		self.assertTrue(doc.grupo_familiar_generado)
		grupo = frappe.get_doc("Grupo Familiar", doc.grupo_familiar_generado)
		self.assertEqual(len(grupo.miembros), 1)

	def test_validar_segundo_menor_reutiliza_tutor_y_grupo(self) -> None:
		sol1 = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222555",
				email="hijo1@example.com",
				dni_tutor="20111666",
				email_tutor="padre@example.com",
			)
		).insert(ignore_permissions=True)
		doc1 = frappe.get_doc(DOCTYPE, sol1.name)
		self._validar(doc1)
		doc1.reload()
		grupo_name = doc1.grupo_familiar_generado

		sol2 = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222666",
				email="hijo2@example.com",
				dni_tutor="20111666",
				email_tutor="padre@example.com",
			)
		).insert(ignore_permissions=True)
		doc2 = frappe.get_doc(DOCTYPE, sol2.name)
		self._validar(doc2)
		doc2.reload()
		self.assertEqual(doc2.grupo_familiar_generado, grupo_name)
		grupo = frappe.get_doc("Grupo Familiar", grupo_name)
		self.assertEqual(len(grupo.miembros), 2)

	def test_validar_idempotente_si_socio_generado(self) -> None:
		sol = insert_solicitud_asociacion(dni="40111666", email="idempot@example.com")
		doc = frappe.get_doc(DOCTYPE, sol.name)
		self._validar(doc)
		doc.reload()
		socio_name = doc.socio_generado
		validado_por = doc.validado_por
		count_users = frappe.db.count("User")

		doc.observaciones_secretaria = "Re-guardado"
		doc.save()
		doc.reload()
		self.assertEqual(doc.socio_generado, socio_name)
		self.assertEqual(doc.validado_por, validado_por)
		self.assertEqual(frappe.db.count("User"), count_users)

	def test_validar_tutor_menor_edad_bloquea(self) -> None:
		sol = frappe.get_doc(
			make_solicitud_menor_payload(
				dni="55222777",
				fecha_nacimiento_tutor=adult_birthdate(17),
			)
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(DOCTYPE, sol.name)
		with self.assertRaises(ValidationError) as ctx:
			self._validar(doc)
		self.assertIn(MSG_TUTOR_MENOR_EDAD, str(ctx.exception))
