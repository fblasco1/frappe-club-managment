"""Tests: corregir medio de pago de un cobro ya registrado.

Spec: `club_management/specs/corregir_medio_pago_cobro.md`
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
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	list_historial_pagos_socio,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
	_default_company,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestCorregirMedioPagoCobro(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.corr.mop@example.com")
		self._item = self._ensure_item("TEST-CORR-MOP", 10000)
		for mode in ("Cash", "Wire Transfer"):
			if not frappe.db.exists("Mode of Payment", mode):
				frappe.get_doc({"doctype": "Mode of Payment", "mode_of_payment": mode}).insert(
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
						"description": "Cuota corr mop",
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _cobrar_cash(self, socio_name: str, invoice: str) -> str:
		frappe.set_user(self._secretaria)
		try:
			return registrar_cobro_manual(socio_name, invoice, mode_of_payment="Cash")
		finally:
			frappe.set_user("Administrator")

	def test_corrige_efectivo_a_transferencia(self) -> None:
		socio = insert_socio(dni="99330001", email="corr.mop.ok@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test corr mop")
		si = self._crear_si(socio.name)
		sync_saldo_deuda_socio(socio.name)
		pe_old = self._cobrar_cash(socio.name, si)

		frappe.set_user(self._secretaria)
		try:
			result = cobranza_desk.corregir_medio_pago(
				payment_entry=pe_old,
				mode_of_payment="Wire Transfer",
				motivo="Error de selección en caja",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["payment_entry_cancelado"], pe_old)
		pe_new = result["payment_entry"]
		self.assertNotEqual(pe_new, pe_old)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_old, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe_new, "docstatus"), 1)
		self.assertEqual(
			frappe.db.get_value("Payment Entry", pe_new, "mode_of_payment"),
			"Wire Transfer",
		)
		self.assertAlmostEqual(
			flt(frappe.db.get_value("Payment Entry", pe_new, "paid_amount")),
			10000.0,
		)
		self.assertAlmostEqual(
			flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si, "outstanding_amount")),
			0.0,
		)

		historial = list_historial_pagos_socio(socio.name)
		vigentes = [r for r in historial if r["payment_entry"] == pe_new]
		self.assertTrue(vigentes)
		self.assertEqual(vigentes[0]["mode_of_payment"], "Wire Transfer")

		comments_old = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Payment Entry", "reference_name": pe_old},
			pluck="content",
		)
		comments_new = frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Payment Entry", "reference_name": pe_new},
			pluck="content",
		)
		self.assertTrue(any(pe_new in (c or "") for c in comments_old))
		self.assertTrue(any(pe_old in (c or "") for c in comments_new))
		self.assertTrue(any("Error de selección" in (c or "") for c in comments_new))
		self.assertIn("recibo", result)
		self.assertEqual(result["recibo"]["comprobante"], pe_new)

	def test_mismo_medio_rechaza(self) -> None:
		socio = insert_socio(dni="99330002", email="corr.mop.same@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test corr same")
		si = self._crear_si(socio.name)
		pe_old = self._cobrar_cash(socio.name, si)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.corregir_medio_pago(
					payment_entry=pe_old,
					mode_of_payment="Cash",
					motivo="sin cambio",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_old, "docstatus"), 1)

	def test_sin_permiso_rechaza(self) -> None:
		socio = insert_socio(dni="99330003", email="corr.mop.perm@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test corr perm")
		si = self._crear_si(socio.name)
		pe_old = self._cobrar_cash(socio.name, si)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				cobranza_desk.corregir_medio_pago(
					payment_entry=pe_old,
					mode_of_payment="Wire Transfer",
					motivo="no autorizado",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_old, "docstatus"), 1)

	def test_pe_con_payment_log_gateway_no_corrigible(self) -> None:
		socio = insert_socio(dni="99330004", email="corr.mop.gw@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test corr gw")
		si = self._crear_si(socio.name)
		pe_old = self._cobrar_cash(socio.name, si)
		record_gateway_transaction(
			merchant_transaction_id=f"SIC-CORR-{pe_old}",
			provider=PROVIDER_SUPERVIELLE,
			sales_invoice=si,
			payment_entry=pe_old,
			socio=socio.name,
			amount=10000,
			status="Conciliado",
			ignore_permissions=True,
		)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.corregir_medio_pago(
					payment_entry=pe_old,
					mode_of_payment="Wire Transfer",
					motivo="gateway",
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Payment Entry", pe_old, "docstatus"), 1)

	def test_motivo_obligatorio(self) -> None:
		socio = insert_socio(dni="99330005", email="corr.mop.motivo@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test corr motivo")
		si = self._crear_si(socio.name)
		pe_old = self._cobrar_cash(socio.name, si)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cobranza_desk.corregir_medio_pago(
					payment_entry=pe_old,
					mode_of_payment="Wire Transfer",
					motivo="   ",
				)
		finally:
			frappe.set_user("Administrator")
