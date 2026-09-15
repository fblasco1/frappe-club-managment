"""Tests GF-6: DocType Finance Settings habilita la visibilidad del módulo Finanzas.

El workspace de Finanzas solo se muestra si su módulo (`Finance`) está en los
módulos permitidos del usuario, y estos se derivan de los DocTypes legibles.
Como el módulo no tenía DocTypes propios, el workspace quedaba oculto para
Tesorería y Secretaría. `Finance Settings` (Single, módulo Finance) con lectura
para esos roles resuelve la visibilidad.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DOCTYPE_JSON = (
	PACKAGE_ROOT / "finance" / "doctype" / "finance_settings" / "finance_settings.json"
)


class TestFinanceSettings(unittest.TestCase):
	def setUp(self) -> None:
		self.assertTrue(DOCTYPE_JSON.exists(), "Falta finance_settings.json")
		self.data = json.loads(DOCTYPE_JSON.read_text(encoding="utf-8"))

	def test_es_single_en_modulo_finance(self) -> None:
		self.assertEqual(self.data.get("module"), "Finance")
		self.assertEqual(self.data.get("is_single"), 1)
		self.assertEqual(self.data.get("name"), "Finance Settings")

	def test_lectura_para_roles_financieros(self) -> None:
		perms = {p["role"]: p for p in self.data.get("permissions", [])}
		for role in ("Tesoreria", "Secretaria", "System Manager"):
			self.assertIn(role, perms, f"Falta permiso para rol {role}")
			self.assertEqual(perms[role].get("read"), 1, f"{role} debe tener lectura")

	def test_secretaria_no_escribe_configuracion(self) -> None:
		# Secretaría solo lee la configuración; no la edita.
		perms = {p["role"]: p for p in self.data.get("permissions", [])}
		self.assertNotEqual(perms["Secretaria"].get("write"), 1)


if __name__ == "__main__":
	unittest.main()
