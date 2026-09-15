"""Tests: Desk no invoca frappe.router.slug() sin argumento.

Spec: `club_management/specs/proyeccion_flujo_fondos.md`
(Scenario: Desk no llama slug sin argumento).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

# slug() sin args (o solo whitespace) rompe Desk: name.toLowerCase() sobre undefined.
_SLUG_NO_ARG = re.compile(
	r"frappe\.router\s*\?\.\s*slug\s*\?\.\s*\(\s*\)|frappe\.router\.slug\s*\(\s*\)"
)


class TestDeskSlugSinArgumento(unittest.TestCase):
	def test_club_desk_navigation_no_llama_slug_vacio(self) -> None:
		js = (PACKAGE_ROOT / "public" / "js" / "club_desk_navigation.js").read_text(
			encoding="utf-8"
		)
		self.assertIsNone(
			_SLUG_NO_ARG.search(js),
			"club_desk_navigation no debe llamar frappe.router.slug() sin argumento",
		)

	def test_inicio_workspace_no_llama_slug_vacio(self) -> None:
		js = (PACKAGE_ROOT / "public" / "js" / "inicio_workspace.js").read_text(encoding="utf-8")
		self.assertIsNone(
			_SLUG_NO_ARG.search(js),
			"inicio_workspace no debe llamar frappe.router.slug() sin argumento",
		)


if __name__ == "__main__":
	unittest.main()
