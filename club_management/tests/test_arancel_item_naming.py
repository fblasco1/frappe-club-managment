"""Tests naming aranceles mensuales (spec arancel_item_naming.md)."""

from __future__ import annotations

import unittest

import frappe

from club_management.activities.data.arancel_item_spec import format_arancel_mensual_item_name
from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_FORMATIVAS_AZUL,
	ITEM_MINIBASQUET,
)
from club_management.activities.services.sync_arancel_item_names import (
	expected_arancel_item_names,
	run_sync_arancel_item_names,
)
from club_management.members.test_helpers import MembersTestCase


class TestFormatArancelMensualItemName(unittest.TestCase):
	def test_formato_completo(self) -> None:
		self.assertEqual(
			format_arancel_mensual_item_name("BASQUET", "MASCULINO", "FORMATIVAS", "AZUL"),
			"ARANCEL MENSUAL - BASQUET/MASCULINO/FORMATIVAS/AZUL",
		)

	def test_omite_vacios_y_normaliza(self) -> None:
		self.assertEqual(
			format_arancel_mensual_item_name("Vóley", None, "", "femenino", "Tira"),
			"ARANCEL MENSUAL - VOLEY/FEMENINO/TIRA",
		)

	def test_actividad_sola(self) -> None:
		self.assertEqual(format_arancel_mensual_item_name("DANZA"), "ARANCEL MENSUAL - DANZA")

	def test_requiere_segmento(self) -> None:
		with self.assertRaises(ValueError):
			format_arancel_mensual_item_name(None, "")


class TestSyncArancelItemNames(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")

	def test_sincroniza_item_name_desde_spec(self) -> None:
		code = ITEM_MINIBASQUET
		if not frappe.db.exists("Item", code):
			self.skipTest(f"Item {code} ausente")
		expected = expected_arancel_item_names()[code]
		frappe.db.set_value("Item", code, "item_name", "NOMBRE VIEJO TEST", update_modified=False)

		result = run_sync_arancel_item_names()

		self.assertEqual(frappe.db.get_value("Item", code, "item_name"), expected)
		self.assertTrue(any(code in u for u in result["updated"]))
		self.assertIn(ITEM_FORMATIVAS_AZUL, expected_arancel_item_names())
