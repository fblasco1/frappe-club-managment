"""Tests de corrección pública por token — Solicitud Asociacion (Sprint 1 Commit 5).

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 5).
"""

from __future__ import annotations

import frappe
from frappe import DoesNotExistError

from club_management.members.api.solicitud_publica import (
	_actualizar_solicitud_impl,
	_consultar_solicitud_impl,
	_confirmar_pago_stub_impl,
)
from club_management.members.services.solicitud_tokens import sign_pago_token
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_SOLICITAR_CORRECCION,
	ACTION_VALIDAR,
	STATE_PENDIENTE,
	STATE_REQUIERE_CORRECCION,
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)
from frappe.model.workflow import apply_workflow


class TestCorreccionPublica(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def test_consultar_solicitud_con_token_valido(self) -> None:
		sol = insert_solicitud_asociacion(dni="60111001", email="cons@example.com")
		result = _consultar_solicitud_impl(sol.token_seguimiento)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["workflow_state"], STATE_PENDIENTE)
		self.assertIn("creation", result)
		self.assertNotIn("dni", result)
		self.assertNotIn("dni_frente", result)
		self.assertNotIn("editable", result)

	def test_consultar_solicitud_token_invalido_404(self) -> None:
		with self.assertRaises(DoesNotExistError):
			_consultar_solicitud_impl("token-inexistente")

	def test_actualizar_solicitud_en_requiere_correccion_pasa_a_pendiente(self) -> None:
		sol = insert_solicitud_asociacion(dni="60111002", email="corr@example.com")
		doc = frappe.get_doc("Solicitud Asociacion", sol.name)
		frappe.set_user(make_secretaria_user())
		apply_workflow(doc, ACTION_SOLICITAR_CORRECCION)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_REQUIERE_CORRECCION)

		consulta = _consultar_solicitud_impl(sol.token_seguimiento)
		self.assertEqual(consulta["workflow_state"], STATE_REQUIERE_CORRECCION)
		self.assertIn("observaciones", consulta)
		self.assertIn("editable", consulta)

		result = _actualizar_solicitud_impl(
			sol.token_seguimiento,
			{"telefono": "+549111000000", "workflow_state": "Validada", "socio_generado": "X"},
		)
		self.assertEqual(result["status"], "ok")
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_PENDIENTE)
		self.assertEqual(doc.telefono, "+549111000000")
		self.assertFalse(doc.socio_generado)
		frappe.set_user("Administrator")

	def test_actualizar_solicitud_token_invalido_404(self) -> None:
		with self.assertRaises(DoesNotExistError):
			_actualizar_solicitud_impl("bad-token", {"telefono": "123"})

	def test_actualizar_solicitud_estado_incorrecto_404(self) -> None:
		sol = insert_solicitud_asociacion(dni="60111003", email="pend@example.com")
		with self.assertRaises(DoesNotExistError):
			_actualizar_solicitud_impl(sol.token_seguimiento, {"telefono": "123"})


class TestPagoStubPublico(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def test_confirmar_pago_stub_activa_socio(self) -> None:
		from unittest.mock import patch

		sol = insert_solicitud_asociacion(dni="70111001", email="pago@example.com")
		doc = frappe.get_doc("Solicitud Asociacion", sol.name)
		frappe.set_user(make_secretaria_user())
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		self.assertTrue(doc.socio_generado)

		pago_token = sign_pago_token(doc.name)
		result = _confirmar_pago_stub_impl(pago_token)
		self.assertEqual(result["status"], "ok")
		socio = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio.estado, "Activo")
		frappe.set_user("Administrator")

	def test_confirmar_pago_token_invalido_404(self) -> None:
		with self.assertRaises(DoesNotExistError):
			_confirmar_pago_stub_impl("token-falso")
