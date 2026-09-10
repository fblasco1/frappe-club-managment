"""Tests BL-6 Fase B: URL del portal y CORS sin wildcard."""

from __future__ import annotations

import frappe

from club_management.activities.services.portal_urls import (
	DEFAULT_PORTAL_SOCIO_URL,
	apply_portal_cors_allowlist,
	build_portal_socio_url,
	portal_allowed_origins,
)
from club_management.members.api.solicitud_publica import _confirmar_pago_stub_impl
from club_management.members.services.solicitud_tokens import sign_pago_token
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_VALIDAR,
	ensure_solicitud_asociacion_workflow,
)
from frappe.model.workflow import apply_workflow
from unittest.mock import patch


class TestPortalSocioUrl(MembersTestCase):
	def tearDown(self) -> None:
		for key in ("portal_socio_url", "allow_cors"):
			if key in frappe.conf:
				del frappe.conf[key]
		if hasattr(frappe.local, "allow_cors"):
			delattr(frappe.local, "allow_cors")
		super().tearDown()

	def test_site_config_no_incluye_token(self) -> None:
		frappe.conf.portal_socio_url = (
			"https://www.icdpedroechague.com.ar/socios/actividades?token=abc&pago_token=xyz"
		)

		url = build_portal_socio_url()

		self.assertEqual(url, "https://www.icdpedroechague.com.ar/socios/actividades")
		self.assertNotIn("token", url.lower())

	def test_origen_sin_path_concatena_area_autenticada(self) -> None:
		frappe.conf.portal_socio_url = "http://localhost:3000/"

		self.assertEqual(
			build_portal_socio_url(),
			"http://localhost:3000/socios/actividades",
		)

	def test_site_config_precede_club_settings(self) -> None:
		settings = frappe.get_single("Club Settings")
		previous = settings.portal_socio_url
		settings.portal_socio_url = "https://www.icdpedroechague.com.ar/socios/actividades"
		settings.save()
		frappe.conf.portal_socio_url = "http://localhost:3000/socios/actividades"
		try:
			self.assertEqual(
				build_portal_socio_url(),
				"http://localhost:3000/socios/actividades",
			)
		finally:
			settings.portal_socio_url = previous
			settings.save()

	def test_default_sin_config(self) -> None:
		settings = frappe.get_single("Club Settings")
		previous = settings.portal_socio_url
		settings.portal_socio_url = ""
		settings.save()
		if "portal_socio_url" in frappe.conf:
			del frappe.conf["portal_socio_url"]
		try:
			self.assertEqual(build_portal_socio_url(), DEFAULT_PORTAL_SOCIO_URL)
		finally:
			settings.portal_socio_url = previous
			settings.save()

	def test_cors_nunca_wildcard(self) -> None:
		frappe.conf.allow_cors = "*"
		frappe.conf.portal_socio_url = "https://www.icdpedroechague.com.ar/socios/actividades"

		origins = portal_allowed_origins()

		self.assertNotIn("*", origins)
		self.assertIn("https://www.icdpedroechague.com.ar", origins)

	def test_club_settings_declara_portal_socio_url(self) -> None:
		field = frappe.get_meta("Club Settings").get_field("portal_socio_url")
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Data")

	def test_apply_portal_cors_allowlist_nunca_wildcard(self) -> None:
		frappe.conf.allow_cors = "*"
		frappe.conf.portal_socio_url = "http://localhost:3000/socios/actividades"

		apply_portal_cors_allowlist()

		self.assertNotIn("*", frappe.local.allow_cors)
		self.assertIn("http://localhost:3000", frappe.local.allow_cors)

	def test_hooks_registra_cors_portal(self) -> None:
		from club_management import hooks

		self.assertIn(
			"club_management.activities.services.portal_urls.apply_portal_cors_allowlist",
			hooks.before_request,
		)


class TestPortalUrlEnPagoStub(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def test_confirmar_pago_devuelve_portal_url_sin_token(self) -> None:
		sol = insert_solicitud_asociacion(dni="78120991", email="portal.url.bl6@example.com")
		doc = frappe.get_doc("Solicitud Asociacion", sol.name)
		frappe.set_user(make_secretaria_user())
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		frappe.set_user("Administrator")

		frappe.conf.portal_socio_url = "http://localhost:3000/socios/actividades"
		try:
			result = _confirmar_pago_stub_impl(sign_pago_token(doc.name))

			self.assertEqual(result["status"], "ok")
			self.assertEqual(result["portal_url"], "http://localhost:3000/socios/actividades")
			self.assertNotIn("token=", result["portal_url"])
			self.assertIn("inscripcion_url", result)
			self.assertIn("token=", result["inscripcion_url"])
		finally:
			if "portal_socio_url" in frappe.conf:
				del frappe.conf["portal_socio_url"]
