"""Tests branding SICLUB en login (spec login_siclub_branding.md)."""

from __future__ import annotations

import os

import frappe

from club_management.members.test_helpers import MembersTestCase


class TestLoginSiclubBranding(MembersTestCase):
	def test_css_siclub_login_existe(self) -> None:
		path = os.path.join(
			frappe.get_app_path("club_management"),
			"public",
			"css",
			"siclub_login.css",
		)
		self.assertTrue(os.path.isfile(path))
		with open(path, encoding="utf-8") as handle:
			content = handle.read()
		self.assertIn("SICLUB", content)
		self.assertIn("Sistema Integral de Gestión de Clubes Deportivos", content)

	def test_hooks_incluye_css_login(self) -> None:
		import club_management.hooks as hooks

		css = hooks.web_include_css
		if isinstance(css, str):
			includes = [css]
		else:
			includes = list(css or [])
		self.assertTrue(
			any("siclub_login.css" in row for row in includes),
			msg=f"web_include_css debe referenciar siclub_login.css: {includes}",
		)
