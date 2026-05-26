"""Tests de Workflow y auditoría — `Solicitud Asociacion` (Sprint 1 Commit 3).

No cubre `validar_solicitud` ni creación de Socio (Commit 4).

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 3).
"""

from __future__ import annotations

import frappe
from frappe.model.workflow import (
	WorkflowTransitionError,
	apply_workflow,
	get_transitions,
	get_workflow,
)

from club_management.members.test_helpers import (
	MembersTestCase,
	apply_workflow_rechazar,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_RECHAZAR,
	ACTION_REENVIAR,
	ACTION_SOLICITAR_CORRECCION,
	ACTION_VALIDAR,
	DOCUMENT_TYPE,
	STATE_PENDIENTE,
	STATE_RECHAZADA,
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

	def test_validar_pasa_a_validada_sin_socio_generado(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		self.assertFalse(doc.socio_generado)

	def test_rechazar_con_motivos_pasa_a_rechazada(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow_rechazar(doc, "Documentación incompleta")
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_RECHAZADA)

	def test_rechazar_sin_motivos_falla_y_mantiene_pendiente(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		workflow = get_workflow(DOCTYPE)
		allowed_actions = {t.action for t in get_transitions(doc, workflow)}
		self.assertNotIn(ACTION_RECHAZAR, allowed_actions)

		with self.assertRaises(WorkflowTransitionError):
			apply_workflow(doc, ACTION_RECHAZAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)


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
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		self.assertEqual(doc.validado_por, self.secretaria)
		self.assertIsNotNone(doc.validado_en)

	def test_rechazar_audita_usuario_y_timestamp(self) -> None:
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow_rechazar(doc, "Falta DNI dorso")
		doc.reload()
		self.assertEqual(doc.rechazado_por, self.secretaria)
		self.assertIsNotNone(doc.rechazado_en)

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
		sol = insert_solicitud_asociacion()
		doc = frappe.get_doc(DOCTYPE, sol.name)
		apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		validado_por = doc.validado_por
		validado_en = doc.validado_en

		doc.observaciones_secretaria = "Nota interna"
		doc.save()
		doc.reload()
		self.assertEqual(doc.validado_por, validado_por)
		self.assertEqual(doc.validado_en, validado_en)
