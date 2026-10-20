"""Tests: cancelar un cobro por mala imputación.

Spec: `club_management/specs/cancelar_pago_mala_imputacion.md`
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, today

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	record_gateway_transaction,
)
from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.api import cobranza_desk
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	list_historial_pagos_socio,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestCancelarPagoMalaImputacion(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.cancel.pe@example.com")
		self._item = self._ensure_item("TEST-CANCEL-PE", 10000)
		if not frappe.db.exists("Mode of Payment", "Cash"):
			frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": "Cash"}).insert(
				ignore_permissions=True
			)

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

	def _crear_si(self, socio_name: str, rate: float = 10000) -> str:
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		doc = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": ensure_customer_for_socio(socio_name, skip_permission_check=True),
				"company": _default_company(),
				"posting_date": today(),
				"due_date": today(),
				"set_posting_time": 1,
				campo: socio_name,
				"items": [
					{
						"item_code": self._item,
						"qty": 1,
						"rate": rate,
						"description": "Cuota cancel pe",
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _cobrar(self, socio_name: str, invoice: str) -> str:
		frappe.set_user(self._secretaria)
		try:
			return registrar_cobro_manual(socio_name, invoice, mode_of_payment="Cash")
		finally:
			frappe.set_user("Administrator")

	def test_cancela_cobro_y_reabre_factura(self) -> None:
		socio = insert_socio(dni="99440001", email="cancel.pe.ok@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test cancel pe")
		si = self._crear_si(socio.name)
		sync_saldo_deuda_socio(socio.name)
		pe_name = self._cobrar(socio.name, si)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
		self.assertAlmostEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si, "outstanding_amount")), 0.0)

		frappe.set_user(self._secretaria)
		try:
			result = cobranza_desk.cancelar_pago(
				payment_entry=pe_name,
				socio=socio.name,
				motivo="Mala imputación: correspondía a otro concepto",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["payment_entry"], pe_name)
		self.assertEqual(result["socio"], socio.name)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 2)
		self.assertAlmostEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si, "outstanding_amount")), 10000.0)
		self.assertAlmostEqual(flt(result["saldo_deuda"]), 10000.0)
		self.assertAlmostEqual(flt(frappe.db.get_value("Socio", socio.name, "saldo_deuda")), 10000.0)

		historial = list_historial_pagos_socio(socio.name)
		self.assertFalse([row for row in historial if row["payment_entry"] == pe_name])

		comments = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Payment Entry", "reference_name": pe_name},
			pluck="content",
		)
		self.assertTrue(any("Mala imputación" in (content or "") for content in comments))

	def test_motivo_vacio_rechaza(self) -> None:
		socio = insert_socio(dni="99440002", email="cancel.pe.motivo@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test cancel motivo")
		si = self._crear_si(socio.name)
		pe_name = self._cobrar(socio.name, si)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.cancelar_pago(payment_entry=pe_name, socio=socio.name, motivo="   ")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
		self.assertAlmostEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si, "outstanding_amount")), 0.0)

	def test_otro_socio_rechaza(self) -> None:
		socio = insert_socio(dni="99440003", email="cancel.pe.owner@example.com")
		otro = insert_socio(dni="99440004", email="cancel.pe.other@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test cancel owner")
		cambiar_estado(otro.name, "Activo", motivo="Test cancel other")
		si = self._crear_si(socio.name)
		pe_name = self._cobrar(socio.name, si)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.cancelar_pago(
					payment_entry=pe_name,
					socio=otro.name,
					motivo="No es de este socio",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)

	def test_pasarela_rechaza(self) -> None:
		socio = insert_socio(dni="99440005", email="cancel.pe.gw@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test cancel gw")
		si = self._crear_si(socio.name)
		pe_name = self._cobrar(socio.name, si)
		record_gateway_transaction(
			merchant_transaction_id=f"SIC-CANCEL-{pe_name}",
			provider=PROVIDER_SUPERVIELLE,
			sales_invoice=si,
			payment_entry=pe_name,
			socio=socio.name,
			amount=10000,
			status="Conciliado",
			ignore_permissions=True,
		)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.cancelar_pago(
					payment_entry=pe_name,
					socio=socio.name,
					motivo="No debería poder",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)

	def test_sin_permiso_rechaza(self) -> None:
		socio = insert_socio(dni="99440006", email="cancel.pe.perm@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test cancel perm")
		si = self._crear_si(socio.name)
		pe_name = self._cobrar(socio.name, si)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				cobranza_desk.cancelar_pago(
					payment_entry=pe_name,
					socio=socio.name,
					motivo="no autorizado",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_name, "docstatus"), 1)
