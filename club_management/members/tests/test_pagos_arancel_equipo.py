"""Tests cálculo de aranceles pagados (spec pagos_por_equipo.md)."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

import frappe

from club_management.members.services.liquidacion_equipo import calcular_pagos_arancel_en_rango


class TestPagosArancelEquipo(TestCase):
	def test_solo_suma_lineas_del_item_arancel(self) -> None:
		invoices = [frappe._dict({"name": "INV-1", "grand_total": 15000, "outstanding_amount": 0})]
		lines = [frappe._dict({"amount": 5000})]

		def fake_get_all(doctype, **kwargs):
			if doctype == "Sales Invoice":
				return invoices
			if doctype == "Sales Invoice Item":
				return lines
			return []

		with (
			patch(
				"club_management.members.services.liquidacion_equipo.erpnext_cobranza_disponible",
				return_value=True,
			),
			patch(
				"club_management.members.services.liquidacion_equipo._campo_socio_en",
				return_value="socio",
			),
			patch("club_management.members.services.liquidacion_equipo.frappe.get_all", side_effect=fake_get_all),
		):
			pagos, count = calcular_pagos_arancel_en_rango(
				"SOC-TEST",
				fecha_desde="2026-03-01",
				fecha_hasta="2026-03-31",
				item_arancel="ARANCEL-TEST",
			)
		self.assertEqual(count, 1)
		self.assertEqual(pagos, 5000.0)

	def test_pago_parcial_proporcional_al_arancel(self) -> None:
		invoices = [frappe._dict({"name": "INV-2", "grand_total": 15000, "outstanding_amount": 7500})]
		lines = [frappe._dict({"amount": 5000})]

		def fake_get_all(doctype, **kwargs):
			if doctype == "Sales Invoice":
				return invoices
			if doctype == "Sales Invoice Item":
				return lines
			return []

		with (
			patch(
				"club_management.members.services.liquidacion_equipo.erpnext_cobranza_disponible",
				return_value=True,
			),
			patch(
				"club_management.members.services.liquidacion_equipo._campo_socio_en",
				return_value="socio",
			),
			patch("club_management.members.services.liquidacion_equipo.frappe.get_all", side_effect=fake_get_all),
		):
			pagos, count = calcular_pagos_arancel_en_rango(
				"SOC-TEST",
				fecha_desde="2026-03-01",
				fecha_hasta="2026-03-31",
				item_arancel="ARANCEL-TEST",
			)
		self.assertEqual(count, 1)
		self.assertEqual(pagos, 2500.0)

	def test_sin_item_arancel_devuelve_cero(self) -> None:
		pagos, count = calcular_pagos_arancel_en_rango(
			"SOC-TEST",
			fecha_desde="2026-03-01",
			fecha_hasta="2026-03-31",
			item_arancel=None,
		)
		self.assertEqual((pagos, count), (0.0, 0))
