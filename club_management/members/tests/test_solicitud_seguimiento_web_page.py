"""Tests de la página pública de seguimiento/corrección de solicitud.

Sprint 1 cierre: portal público basado en token para consultar estado y reenviar
correcciones cuando `workflow_state == "Requiere Corrección"`.
"""

from __future__ import annotations

import os

import frappe
from frappe.tests.utils import FrappeTestCase

CONSULTAR_METHOD = "club_management.members.api.solicitud_publica.consultar_solicitud"
ACTUALIZAR_METHOD = "club_management.members.api.solicitud_publica.actualizar_solicitud"


def _seguimiento_web_page_path() -> str:
	return os.path.join(
		frappe.get_app_path("club_management"),
		"www",
		"solicitud-seguimiento.html",
	)


class TestSolicitudSeguimientoWebPage(FrappeTestCase):
	def test_archivo_plantilla_existe(self) -> None:
		self.assertTrue(
			os.path.isfile(_seguimiento_web_page_path()),
			"Debe existir www/solicitud-seguimiento.html en el paquete club_management",
		)

	def test_plantilla_declara_metodos_publicos(self) -> None:
		with open(_seguimiento_web_page_path(), encoding="utf-8") as f:
			body = f.read()
		self.assertIn(CONSULTAR_METHOD, body)
		self.assertIn(ACTUALIZAR_METHOD, body)
		self.assertIn("URLSearchParams", body)
		self.assertIn(".get(\"token\")", body)

	def test_plantilla_no_usa_innerhtml_para_motivos(self) -> None:
		with open(_seguimiento_web_page_path(), encoding="utf-8") as f:
			body = f.read()
		self.assertIn("textContent", body)
		self.assertNotIn("innerHTML", body)

