"""Tests sidebar Desk del workspace Secretaría.

Spec: `club_management/specs/mvp_operacion_secretaria_sin_pagos.md` (sidebar).
"""

from __future__ import annotations

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
from club_management.members.setup.secretaria_workspace import WORKSPACE_NAME
from club_management.members.setup.secretaria_workspace_sidebar import (
	HIDDEN_SIDEBAR_LINKS,
	SIDEBAR_ITEMS,
	secretaria_sidebar_fixture_path,
	sync_secretaria_workspace_sidebar,
)


class TestSecretariaWorkspaceSidebar(FrappeTestCase):
	def test_fixture_sidebar_tiene_secretaria_socio_e_informes(self) -> None:
		path = secretaria_sidebar_fixture_path()
		self.assertTrue(os.path.isfile(path))
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("title"), WORKSPACE_NAME)
		self.assertEqual(data.get("app"), "club_management")
		labels = [row.get("label") for row in data.get("items") or []]
		self.assertEqual(labels[0], "Secretaría")
		self.assertIn("Socio", labels)
		self.assertIn("Valores de Cuota Social", labels)
		self.assertIn("Informes", labels)
		for report_name in CLUB_DESK_REPORTS:
			self.assertIn(report_name, labels)
		for hidden in HIDDEN_SIDEBAR_LINKS:
			self.assertNotIn(hidden, labels)

	def test_setup_constants_alineadas_al_fixture(self) -> None:
		labels = [row["label"] for row in SIDEBAR_ITEMS]
		self.assertIn("Secretaría", labels)
		self.assertIn("Socio", labels)
		self.assertIn("Valores de Cuota Social", labels)
		self.assertIn("Informes", labels)
		for hidden in HIDDEN_SIDEBAR_LINKS:
			self.assertNotIn(hidden, labels)

	def test_fixture_workspace_sin_enlaces_de_informes(self) -> None:
		path = os.path.join(
			frappe.get_app_path("club_management"),
			"members",
			"workspace",
			"secretaria",
			"secretaria.json",
		)
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		link_targets = {row.get("link_to") for row in data.get("links") or []}
		for report_name in CLUB_DESK_REPORTS:
			self.assertNotIn(report_name, link_targets)

	def test_sync_sidebar_en_sitio(self) -> None:
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			self.skipTest("Ejecutar bench migrate para sincronizar workspaces")
		sync_secretaria_workspace_sidebar()
		if not frappe.db.exists("Workspace Sidebar", WORKSPACE_NAME):
			self.skipTest("Workspace Sidebar no sincronizado")
		items = frappe.get_all(
			"Workspace Sidebar Item",
			filters={"parent": WORKSPACE_NAME},
			fields=["label", "link_to", "link_type", "type", "child"],
			order_by="idx asc",
		)
		labels = [row["label"] for row in items]
		self.assertIn("Secretaría", labels)
		self.assertIn("Socio", labels)
		self.assertIn("Valores de Cuota Social", labels)
		self.assertIn("Informes", labels)
		for hidden in HIDDEN_SIDEBAR_LINKS:
			self.assertNotIn(hidden, labels)
		informes_idx = next(i for i, row in enumerate(items) if row["label"] == "Informes")
		self.assertEqual(items[informes_idx]["type"], "Section Break")
		report_rows = [row for row in items if row.get("link_type") == "Report"]
		self.assertGreaterEqual(len(report_rows), 1)
		for row in report_rows:
			self.assertEqual(row.get("child"), 1)
