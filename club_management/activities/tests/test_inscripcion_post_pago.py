"""Tests del flujo post-pago: inscripción a actividades."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.exceptions import DoesNotExistError, ValidationError

from club_management.activities.api.inscripcion_publica import confirmar_inscripcion_actividades
from club_management.activities.services.actividades_catalog import ESTADO_SOCIO_PENDIENTE_INSCRIPCION
from club_management.activities.services.inscripcion_socio import (
	actividades_resumen_socio,
	confirmar_inscripcion_post_pago,
)
from club_management.members.api.solicitud_publica import _confirmar_pago_stub_impl
from club_management.members.services.solicitud_tokens import sign_pago_token
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_VALIDAR,
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)
from frappe.model.workflow import apply_workflow


class TestInscripcionPostPago(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def _validar_solicitud(self, sol_name: str) -> frappe.model.document.Document:
		doc = frappe.get_doc("Solicitud Asociacion", sol_name)
		frappe.set_user(make_secretaria_user())
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		frappe.set_user("Administrator")
		return doc

	def test_confirmar_pago_deja_pendiente_inscripcion(self) -> None:
		sol = insert_solicitud_asociacion(dni="70991001", email="ins.pago@example.com")
		doc = self._validar_solicitud(sol.name)
		self.assertEqual(doc.workflow_state, STATE_VALIDADA)

		result = _confirmar_pago_stub_impl(sign_pago_token(doc.name))
		self.assertEqual(result["status"], "ok")
		self.assertIn("inscripcion_url", result)

		socio = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio.estado, ESTADO_SOCIO_PENDIENTE_INSCRIPCION)

	def test_inscripcion_actividades_activa_socio(self) -> None:
		sol = insert_solicitud_asociacion(dni="70991002", email="ins.act@example.com")
		doc = self._validar_solicitud(sol.name)
		token = sign_pago_token(doc.name)
		_confirmar_pago_stub_impl(token)

		actividad = "Inscripcion Post Pago Test"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 0,
					"orden": 999,
				}
			).insert(ignore_permissions=True)

		result = confirmar_inscripcion_post_pago(doc.name, [actividad])
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["actividad_resumen"], actividad)

		socio = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(socio.actividad, actividad)
		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": socio.name, "estado": "Activa"}),
			1,
		)

	def test_inscripcion_vacia_activa_sin_actividades(self) -> None:
		sol = insert_solicitud_asociacion(dni="70991003", email="ins.vacia@example.com")
		doc = self._validar_solicitud(sol.name)
		_confirmar_pago_stub_impl(sign_pago_token(doc.name))

		confirmar_inscripcion_post_pago(doc.name, [])
		socio = frappe.get_doc("Socio", doc.socio_generado)
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(actividades_resumen_socio(socio.name), "")

	def test_no_reinscribe_si_ya_activo(self) -> None:
		sol = insert_solicitud_asociacion(dni="70991004", email="ins.dup@example.com")
		doc = self._validar_solicitud(sol.name)
		token = sign_pago_token(doc.name)
		_confirmar_pago_stub_impl(token)
		confirmar_inscripcion_post_pago(doc.name, [])

		with self.assertRaises(ValidationError):
			confirmar_inscripcion_post_pago(doc.name, [])

	def test_token_invalido_404(self) -> None:
		with self.assertRaises(DoesNotExistError):
			confirmar_inscripcion_actividades("token-invalido", [])
