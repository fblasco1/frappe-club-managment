"""Tests de emails y stub de pago — Solicitud Asociacion (Sprint 1 Commit 5).

Spec: `club_management/specs/solicitud_asociacion_publica.md` (Commit 5).
"""

from __future__ import annotations

import re
from unittest.mock import patch
from urllib.parse import unquote

import frappe

from club_management.members.email_templates.solicitud_emails import (
	render_solicitud_validada_email,
)
from club_management.members.services.solicitud_tokens import sign_pago_token, verify_pago_token
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_solicitud_asociacion,
)


class TestSolicitudAsociacionEmails(MembersTestCase):
	"""Plantillas y tokens de pago."""

	def test_email_validada_solo_nombre_y_link_sin_dni(self) -> None:
		html = render_solicitud_validada_email(
			nombre="Ana",
			pago_url="https://example.com/pago-stub?token=abc",
		)
		self.assertIn("Ana", html)
		self.assertIn("Pagar primera cuota", html)
		self.assertNotIn("30123456", html)

	def test_pago_token_no_es_adivinable_por_enumeracion(self) -> None:
		sol1 = insert_solicitud_asociacion(dni="50111001", email="tok1@example.com")
		sol2 = insert_solicitud_asociacion(dni="50111002", email="tok2@example.com")
		token1 = sign_pago_token(sol1.name)
		token2 = sign_pago_token(sol2.name)
		self.assertNotEqual(token1, token2)
		self.assertEqual(verify_pago_token(token1), sol1.name)
		self.assertEqual(verify_pago_token(token2), sol2.name)
		self.assertIsNone(verify_pago_token("token-inventado"))

	@patch("frappe.sendmail")
	def test_send_validacion_incluye_link_stub_firmado(self, mock_sendmail) -> None:
		from club_management.members.services.solicitud_notificaciones import (
			_send_validacion_pago_email,
		)

		sol = insert_solicitud_asociacion(dni="50111003", email="mail@example.com")
		_send_validacion_pago_email(sol.name, "mail@example.com")
		mock_sendmail.assert_called_once()
		html = mock_sendmail.call_args.kwargs.get("message") or mock_sendmail.call_args[1].get("message")
		self.assertIn("/pago-stub?token=", html)
		match = re.search(r"/pago-stub\?token=([^\"]+)", html)
		self.assertIsNotNone(match)
		token_param = unquote(match.group(1))
		self.assertEqual(verify_pago_token(token_param), sol.name)
		self.assertIn("Ana", html)
