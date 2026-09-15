"""Tests del workspace Desk «Secretaría».

Spec: `club_management/specs/socios_categoria_validacion.md` (panel Secretaría).
"""

from __future__ import annotations

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.members.setup.inicio_workspace import INICIO_WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME
from club_management.members.test_helpers import ensure_role_secretaria_exists


def _workspace_json_path() -> str:
	return os.path.join(
		frappe.get_app_path("club_management"),
		"members",
		"workspace",
		"secretaria",
		"secretaria.json",
	)


class TestSecretariaWorkspace(FrappeTestCase):
	def test_fixture_workspace_sin_widgets_nativos(self) -> None:
		with open(_workspace_json_path(), encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(json.loads(data.get("content") or "[]"), [])
		self.assertEqual(data.get("number_cards") or [], [])

	def test_fixture_workspace_sin_solicitudes_ni_grupo_familiar(self) -> None:
		path = _workspace_json_path()
		self.assertTrue(os.path.isfile(path))
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("label"), WORKSPACE_NAME)
		self.assertEqual(data.get("module"), "Members")
		link_targets = {row.get("link_to") for row in data.get("links") or []}
		self.assertNotIn("Solicitud Asociacion", link_targets)
		self.assertNotIn("Grupo Familiar", link_targets)
		shortcuts = data.get("shortcuts") or []
		labels = {row.get("label") for row in shortcuts}
		self.assertNotIn("Solicitudes pendientes", labels)

	def test_workspace_sincronizado_en_sitio(self) -> None:
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			self.skipTest("Ejecutar bench migrate para sincronizar el workspace Secretaría")
		ws = frappe.get_doc("Workspace", WORKSPACE_NAME)
		self.assertEqual(ws.module, "Members")
		roles = {row.role for row in ws.roles}
		self.assertIn("Secretaria", roles)

	def test_workspace_secretaria_sigue_disponible(self) -> None:
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			self.skipTest("Workspace Secretaría no sincronizado")
		self.assertTrue(frappe.db.exists("Workspace", INICIO_WORKSPACE_NAME))
