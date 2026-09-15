"""Tests medios de pago Desk (gráficos y cobranza manual)."""

from __future__ import annotations

import frappe

from club_management.members.services.modos_pago_desk import (
	agrupar_modo_pago_chart,
	list_modos_pago_cobranza_payload,
	validar_modo_pago_desk,
)
from club_management.members.test_helpers import MembersTestCase


class TestModosPagoDesk(MembersTestCase):
	def test_agrupar_modo_pago_chart(self) -> None:
		self.assertEqual(agrupar_modo_pago_chart("Cash"), "efectivo")
		self.assertEqual(agrupar_modo_pago_chart("Credit Card"), "tarjeta")
		self.assertEqual(agrupar_modo_pago_chart("Wire Transfer"), "transferencia")
		self.assertEqual(agrupar_modo_pago_chart("Unknown"), "otro")

	def test_list_modos_pago_cobranza_incluye_efectivo(self) -> None:
		if not frappe.db.exists("Mode of Payment", "Cash"):
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": "Cash"}).insert(
				ignore_permissions=True
			)
		items = list_modos_pago_cobranza_payload()
		values = {row["value"] for row in items}
		self.assertIn("Cash", values)

	def test_validar_modo_pago_desk_rechaza_desconocido(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			validar_modo_pago_desk("Modo Inventado XYZ")
