"""Tests GF-6: permisos operativos de Finanzas para Secretaría (lógica pura)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from club_management.finance.setup.secretaria_finance_permissions import (
	DOCTYPES_EN_MODO_CUSTOM,
	OPERATIVE_PERMS,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class TestSecretariaFinancePerms(unittest.TestCase):
	def test_solo_toca_doctypes_en_modo_custom(self) -> None:
		# No agregar Custom DocPerm a DocTypes con permisos estándar (los borraría).
		for doctype in OPERATIVE_PERMS:
			self.assertIn(
				doctype,
				DOCTYPES_EN_MODO_CUSTOM,
				f"{doctype} no está en modo custom: agregar Custom DocPerm rompería sus permisos estándar",
			)

	def test_factura_compra_operativa(self) -> None:
		pi = OPERATIVE_PERMS["Purchase Invoice"]
		for flag in ("read", "create", "write", "submit"):
			self.assertEqual(pi.get(flag), 1, f"Falta permiso {flag} en Purchase Invoice")

	def test_pago_operativo(self) -> None:
		pe = OPERATIVE_PERMS["Payment Entry"]
		for flag in ("read", "create", "write", "submit"):
			self.assertEqual(pe.get(flag), 1, f"Falta permiso {flag} en Payment Entry")

	def test_masters_solo_lectura(self) -> None:
		for master in ("Item", "Account", "Cost Center", "Company", "Mode of Payment"):
			perms = OPERATIVE_PERMS[master]
			self.assertEqual(perms.get("read"), 1, f"{master} debe ser legible")
			self.assertNotEqual(perms.get("create"), 1, f"{master} no debe ser creable por Secretaría")
			self.assertNotEqual(perms.get("write"), 1, f"{master} no debe ser editable por Secretaría")

	def test_no_incluye_flujo_ni_reportes_pyl(self) -> None:
		# Secretaría no recibe permiso operativo sobre reportes/flujo (siguen por rol).
		self.assertNotIn("Proyeccion Flujo de Fondos", OPERATIVE_PERMS)
		self.assertNotIn("GL Entry", OPERATIVE_PERMS)

	def test_workspace_incluye_rol_secretaria(self) -> None:
		data = json.loads(
			(PACKAGE_ROOT / "finance" / "workspace" / "tesoreria" / "tesoreria.json").read_text(
				encoding="utf-8"
			)
		)
		roles = {r.get("role") for r in data.get("roles", [])}
		self.assertIn("Secretaria", roles)
		self.assertIn("Tesoreria", roles)


if __name__ == "__main__":
	unittest.main()
