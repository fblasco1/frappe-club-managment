"""Tests de la página pública `/pago-stub` (contexto Jinja + token)."""

from __future__ import annotations

import os
from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from club_management.members.services.solicitud_tokens import (
	build_pago_stub_url,
	normalize_pago_token_from_request,
	sign_pago_token,
	verify_pago_token,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_VALIDAR,
	ensure_solicitud_asociacion_workflow,
)


def _pago_stub_py_path() -> str:
	return os.path.join(frappe.get_app_path("club_management"), "www", "pago_stub.py")


class TestPagoStubWebPage(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def test_modulo_python_usa_nombre_frappe_www(self) -> None:
		"""Frappe resuelve `pago-stub.html` → `pago_stub.py` (no `pago-stub.py`)."""
		self.assertTrue(
			os.path.isfile(_pago_stub_py_path()),
			"Debe existir www/pago_stub.py para que get_context se ejecute",
		)

	def test_get_context_marca_enlace_valido_con_token_firmado(self) -> None:
		from club_management.www import pago_stub

		sol = insert_solicitud_asociacion(dni="70112001", email="stub.web@example.com")
		doc = frappe.get_doc("Solicitud Asociacion", sol.name)
		frappe.set_user(make_secretaria_user())
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		frappe.set_user("Administrator")

		token = sign_pago_token(doc.name)
		frappe.form_dict["token"] = token
		ctx = frappe._dict()
		pago_stub.get_context(ctx)
		self.assertTrue(ctx.pago_valido)
		self.assertEqual(ctx.pago_token, token)
		self.assertIn(doc.nombre, ctx.nombre_solicitante)

	def test_build_pago_stub_url_codifica_token_y_verifica(self) -> None:
		sol = insert_solicitud_asociacion(dni="70112002", email="url@example.com")
		token = sign_pago_token(sol.name)
		url = build_pago_stub_url(token, base_url="http://dev.localhost:8000")
		self.assertIn("/pago-stub?token=", url)
		raw = url.split("token=", 1)[1]
		normalized = normalize_pago_token_from_request(raw)
		self.assertEqual(verify_pago_token(normalized), sol.name)
