"""Tests recordatorio provisión sueldos — último día hábil."""

from __future__ import annotations

import frappe
from frappe.utils import getdate

from club_management.finance.services.recordatorio_sueldos import (
	get_recordatorio_provision_sueldos_payload,
	get_ultimo_dia_habil_mes,
	is_ultimo_dia_habil,
)
from club_management.members.services.secretaria_workspace_panel import get_panel_lists_payload
from club_management.members.test_helpers import MembersTestCase


class TestRecordatorioSueldos(MembersTestCase):
	def test_ultimo_dia_habil_enero_2026_es_viernes_30(self) -> None:
		# 31/01/2026 es sábado → último hábil es 30/01/2026
		self.assertEqual(str(get_ultimo_dia_habil_mes("2026-01-15")), "2026-01-30")

	def test_is_ultimo_dia_habil_true(self) -> None:
		self.assertTrue(is_ultimo_dia_habil("2026-01-30"))

	def test_is_ultimo_dia_habil_false(self) -> None:
		self.assertFalse(is_ultimo_dia_habil("2026-01-29"))

	def test_no_muestra_fuera_de_ultimo_dia_habil(self) -> None:
		payload = get_recordatorio_provision_sueldos_payload(reference_date="2026-01-15")
		self.assertFalse(payload["mostrar"])

	def test_muestra_en_ultimo_dia_habil(self) -> None:
		if not frappe.db.exists("DocType", "Purchase Invoice"):
			self.skipTest("ERPNext no instalado")
		payload = get_recordatorio_provision_sueldos_payload(reference_date="2026-01-30")
		self.assertTrue(payload["mostrar"])
		self.assertTrue(payload["es_ultimo_dia_habil"])

	def test_panel_lists_incluye_recordatorio(self) -> None:
		data = get_panel_lists_payload(reference_date="2026-01-30")
		self.assertIn("recordatorio_sueldos", data)
		self.assertIn("mostrar", data["recordatorio_sueldos"])
