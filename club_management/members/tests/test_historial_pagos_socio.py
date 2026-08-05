"""Tests: historial de pagos en Socio.

Spec: `club_management/specs/historial_pagos_socio.md`
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	list_historial_pagos_socio,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestHistorialPagosSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.historial.pagos@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)

	def _ensure_item(self, code: str, rate: float) -> str:
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "Products",
					"stock_uom": "Nos",
					"is_sales_item": 1,
					"is_stock_item": 0,
					"standard_rate": rate,
				}
			).insert(ignore_permissions=True)
		return code

	def _crear_si(self, socio_name: str, item_code: str, rate: float) -> str:
		from club_management.members.services.cobranza_manual import (
			_default_company,
			ensure_customer_for_socio,
		)

		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio_name)
		posting = today()
		doc = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": posting,
				"due_date": posting,
				"set_posting_time": 1,
				campo: socio_name,
				"items": [{"item_code": item_code, "qty": 1, "rate": rate, "description": "Cuota test"}],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_historial_incluye_pago_del_socio(self) -> None:
		socio = insert_socio(dni="99220001", email="hist.ok@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test historial")
		item = self._ensure_item("TEST-HIST-PAGO", 3000)
		si = self._crear_si(socio.name, item, 3000)
		sync_saldo_deuda_socio(socio.name)

		frappe.set_user(self._secretaria)
		try:
			pe = registrar_cobro_manual(socio.name, si, mode_of_payment="Cash")
			rows = list_historial_pagos_socio(socio.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(rows)
		self.assertEqual(rows[0]["payment_entry"], pe)
		self.assertEqual(rows[0]["mode_of_payment"], "Cash")
		self.assertAlmostEqual(flt(rows[0]["paid_amount"]), 3000.0)
		self.assertIn(si, rows[0]["sales_invoices"])

	def test_historial_no_cruza_otro_socio(self) -> None:
		a = insert_socio(dni="99220002", email="hist.a@example.com")
		b = insert_socio(dni="99220003", email="hist.b@example.com")
		cambiar_estado(a.name, "Activo", motivo="Test hist a")
		cambiar_estado(b.name, "Activo", motivo="Test hist b")
		item = self._ensure_item("TEST-HIST-ISO", 1500)
		si_a = self._crear_si(a.name, item, 1500)
		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_manual(a.name, si_a, mode_of_payment="Cash")
			rows_b = list_historial_pagos_socio(b.name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(rows_b, [])


if __name__ == "__main__":
	import unittest

	unittest.main()
