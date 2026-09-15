"""Tests: navegación Desk Actividades (tabs + sidebar).

Spec: `club_management/specs/navegacion_actividades_desk.md`
"""

from __future__ import annotations

import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NAV_JS = PACKAGE_ROOT / "public" / "js" / "club_desk_navigation.js"


class TestNavegacionActividadesDesk(unittest.TestCase):
	def setUp(self) -> None:
		self.js = NAV_JS.read_text(encoding="utf-8")

	def test_define_doctypes_actividades(self) -> None:
		self.assertIn("CLUB_ACTIVIDADES_DOCTYPES", self.js)
		for dt in (
			"Actividad",
			"Grupo Actividad",
			"Equipo Actividad",
			"Inscripcion Actividad",
		):
			self.assertIn(dt, self.js)

	def test_is_club_desk_page_incluye_actividad(self) -> None:
		self.assertIn("is_club_actividad_page", self.js)
		# is_club_desk_page debe componer is_club_actividad_page
		start = self.js.index("is_club_desk_page = function")
		block = self.js[start : start + 400]
		self.assertIn("is_club_actividad_page", block)

	def test_refresh_sidebar_pages_y_doctypes_actividades(self) -> None:
		start = self.js.index("refresh_sidebar = function")
		block = self.js[start : start + 1200]
		self.assertIn("CLUB_PAGES_ACTIVIDADES", block)
		self.assertIn("is_club_actividad_page", block)
		self.assertIn("actividades_sidebar", block)

	def test_get_active_tab_actividades_para_doctypes(self) -> None:
		start = self.js.index("get_active_tab = function")
		block = self.js[start : start + 900]
		self.assertIn("is_club_actividad_page", block)
		self.assertIn('tab === "actividades"', block)


if __name__ == "__main__":
	unittest.main()
