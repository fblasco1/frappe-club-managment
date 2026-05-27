"""Flujo E2E Solicitud de Asociación — CI (API, sin navegador).

Spec: `specs/solicitud_asociacion_publica.md` — «Flujo E2E — CI y Q&A supervisado».
"""

from __future__ import annotations

import frappe

from club_management.members.qa.flujo_solicitud import FlujoSolicitudRunner
from club_management.members.test_helpers import MembersTestCase, ensure_role_socio_exists
from club_management.members.workflow.solicitud_asociacion_workflow import (
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)


class TestFlujoSolicitudCompleto(MembersTestCase):
	"""Recorrido de punta a punta equivalente al testeo manual en Desk."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()
		ensure_role_socio_exists()

	def test_flujo_feliz_adulto_hasta_socio_activo(self) -> None:
		runner = FlujoSolicitudRunner(
			dni="80999001",
			email="flujo.ci.01@example.com",
		)
		result = runner.run_happy_path_adulto()

		self.assertTrue(result.token_seguimiento)
		self.assertTrue(result.socio_name)
		doc = frappe.get_doc("Solicitud Asociacion", result.solicitud_name)
		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		socio = frappe.get_doc("Socio", result.socio_name)
		self.assertEqual(socio.estado, "Activo")
		self.assertEqual(socio.solicitud_origen, result.solicitud_name)
		self.assertEqual(len(result.steps), 4)

	def test_flujo_con_correccion_antes_de_validar(self) -> None:
		runner = FlujoSolicitudRunner(
			dni="80999002",
			email="flujo.ci.02@example.com",
		)
		result = runner.run_path_con_correccion()

		doc = frappe.get_doc("Solicitud Asociacion", result.solicitud_name)
		self.assertEqual(doc.telefono, "+549119998877")
		socio = frappe.get_doc("Socio", result.socio_name)
		self.assertEqual(socio.estado, "Activo")
