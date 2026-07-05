"""Tests página Desk Valores de Cuota Social.

Spec: `club_management/specs/valores_cuota_social_page.md`.
"""

from __future__ import annotations

import json
import os

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.members.setup.secretaria_workspace_sidebar import (
	SIDEBAR_ITEMS,
	VALORES_CUOTA_SOCIAL_PAGE,
	valores_cuota_social_page_fixture_path,
)


class TestValoresCuotaSocialPage(MembersTestCase):
	def test_fixture_pagina_existe(self) -> None:
		path = valores_cuota_social_page_fixture_path()
		self.assertTrue(os.path.isfile(path))
		with open(path, encoding="utf-8") as handle:
			data = json.load(handle)
		self.assertEqual(data.get("name"), VALORES_CUOTA_SOCIAL_PAGE)
		self.assertEqual(data.get("title"), "Valores de Cuota Social")
		roles = {row.get("role") for row in data.get("roles") or []}
		self.assertIn("Secretaria", roles)

	def test_sidebar_incluye_valores_cuota_social(self) -> None:
		labels = [row["label"] for row in SIDEBAR_ITEMS]
		self.assertIn("Valores de Cuota Social", labels)
		item = next(row for row in SIDEBAR_ITEMS if row["label"] == "Valores de Cuota Social")
		self.assertEqual(item["link_type"], "Page")
		self.assertEqual(item["link_to"], VALORES_CUOTA_SOCIAL_PAGE)

	def test_pagina_registrada_tras_migrate(self) -> None:
		if not frappe.db.exists("Page", VALORES_CUOTA_SOCIAL_PAGE):
			self.skipTest("Ejecutar bench migrate para importar la página")
		title = frappe.db.get_value("Page", VALORES_CUOTA_SOCIAL_PAGE, "title")
		self.assertEqual(title, "Valores de Cuota Social")
