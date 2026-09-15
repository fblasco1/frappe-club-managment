"""Tests: cobro multi-factura y medios mixtos.

Spec: `club_management/specs/cobro_multi_factura_medios_mixtos.md`
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_reference_no_cobro,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	generar_cargo_socio,
	list_facturas_pendientes_socio,
	registrar_cobro_compuesto,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestCobroMultiFacturaMediosMixtos(MembersTestCase):
	_REFERENCE = "2026-07-01"

	def test_reference_no_no_supera_140(self) -> None:
		names = [f"ACC-SINV-2026-{i:05d}" for i in range(160, 172)]
		ref = _reference_no_cobro(names)
		self.assertLessEqual(len(ref), 140)
		self.assertTrue(ref.startswith("ACC-SINV-2026-00160"))
		self.assertIn("facturas", ref.lower())
		# Una sola SI: nombre completo (si cabe).
		self.assertEqual(_reference_no_cobro(["ACC-SINV-2026-00001"]), "ACC-SINV-2026-00001")

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.cobro.mixto@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		settings.save(ignore_permissions=True)

	def _socio_activo(self, *, dni: str, email: str):
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test cobro mixto")
		return socio

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

	def _crear_si(self, socio_name: str, item_code: str, rate: float, *, remarks: str) -> str:
		from frappe.utils import today

		from club_management.members.services.cobranza_manual import (
			_default_company,
			ensure_customer_for_socio,
		)

		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		self.assertTrue(campo)
		customer = ensure_customer_for_socio(socio_name)
		posting = today()
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": customer,
			"company": _default_company(),
			"posting_date": posting,
			"due_date": posting,
			"set_posting_time": 1,
			campo: socio_name,
			"remarks": remarks,
			"items": [{"item_code": item_code, "qty": 1, "rate": rate}],
		}
		campo_periodo = _campo_periodo_cobro()
		if campo_periodo:
			payload[campo_periodo] = format_periodo_cobro(self._REFERENCE)
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_generar_cargo_emite_una_factura_por_concepto(self) -> None:
		"""Dos ítems en el builder → dos SI (no una con dos líneas)."""
		socio = self._socio_activo(dni="99110001", email="multi.gen@example.com")
		item_a = self._ensure_item("TEST-COBRO-CONCEPTO-A", 1000)
		item_b = self._ensure_item("TEST-COBRO-CONCEPTO-B", 2500)

		from club_management.members.services import cobranza_manual as cm

		original = cm.build_invoice_items_for_socio

		def _fake_items(*_a, **_k):
			return [
				{"item_code": item_a, "qty": 1, "rate": 1000, "description": "Cuota social"},
				{"item_code": item_b, "qty": 1, "rate": 2500, "description": "Arancel actividad"},
			]

		cm.build_invoice_items_for_socio = _fake_items  # type: ignore[method-assign]
		try:
			frappe.set_user(self._secretaria)
			try:
				names = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
			finally:
				frappe.set_user("Administrator")
		finally:
			cm.build_invoice_items_for_socio = original  # type: ignore[method-assign]

		self.assertIsInstance(names, list)
		self.assertEqual(len(names), 2)
		for name in names:
			self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 1)
			n_items = frappe.db.count("Sales Invoice Item", {"parent": name})
			self.assertEqual(n_items, 1)
		self.assertAlmostEqual(sync_saldo_deuda_socio(socio.name), 3500.0)

	def test_registrar_cobro_varias_facturas_un_medio(self) -> None:
		socio = self._socio_activo(dni="99110002", email="multi.simple@example.com")
		item_a = self._ensure_item("TEST-COBRO-A", 4000)
		item_b = self._ensure_item("TEST-COBRO-B", 6000)
		si_a = self._crear_si(socio.name, item_a, 4000, remarks="Cuota")
		si_b = self._crear_si(socio.name, item_b, 6000, remarks="Arancel")
		sync_saldo_deuda_socio(socio.name)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro_compuesto(
				socio.name,
				[si_a, si_b],
				[{"mode_of_payment": "Cash", "amount": 10000}],
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(len(result["payment_entries"]), 1)
		pe = result["payment_entries"][0]
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "docstatus"), 1)
		self.assertEqual(frappe.db.get_value("Payment Entry", pe, "mode_of_payment"), "Cash")
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_a, "outstanding_amount")), 0)
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_b, "outstanding_amount")), 0)
		self.assertEqual(flt(frappe.db.get_value("Socio", socio.name, "saldo_deuda")), 0)

	def test_registrar_cobro_mixto_dos_medios(self) -> None:
		socio = self._socio_activo(dni="99110003", email="multi.mix@example.com")
		item_a = self._ensure_item("TEST-COBRO-MIX-A", 10000)
		item_b = self._ensure_item("TEST-COBRO-MIX-B", 5000)
		si_a = self._crear_si(socio.name, item_a, 10000, remarks="Cuota")
		si_b = self._crear_si(socio.name, item_b, 5000, remarks="Arancel")
		sync_saldo_deuda_socio(socio.name)

		frappe.set_user(self._secretaria)
		try:
			result = registrar_cobro_compuesto(
				socio.name,
				[si_a, si_b],
				[
					{"mode_of_payment": "Cash", "amount": 10000},
					{"mode_of_payment": "Wire Transfer", "amount": 5000},
				],
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(len(result["payment_entries"]), 2)
		modes = {
			frappe.db.get_value("Payment Entry", pe, "mode_of_payment")
			for pe in result["payment_entries"]
		}
		self.assertEqual(modes, {"Cash", "Wire Transfer"})
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_a, "outstanding_amount")), 0)
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_b, "outstanding_amount")), 0)

	def test_rechaza_suma_medios_distinta(self) -> None:
		socio = self._socio_activo(dni="99110004", email="multi.badsum@example.com")
		item_a = self._ensure_item("TEST-COBRO-BAD", 8000)
		si_a = self._crear_si(socio.name, item_a, 8000, remarks="Cuota")

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				registrar_cobro_compuesto(
					socio.name,
					[si_a],
					[{"mode_of_payment": "Cash", "amount": 7000}],
				)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_a, "outstanding_amount")), 8000)

	def test_compat_registrar_cobro_manual_unitario(self) -> None:
		socio = self._socio_activo(dni="99110005", email="multi.compat@example.com")
		names = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(names)
		invoice_name = names[0] if isinstance(names, list) else names

		frappe.set_user(self._secretaria)
		try:
			pe = registrar_cobro_manual(socio.name, invoice_name, mode_of_payment="Cash")
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(pe)
		self.assertEqual(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount")), 0)

	def test_list_facturas_incluye_concepto(self) -> None:
		socio = self._socio_activo(dni="99110006", email="multi.list@example.com")
		item_a = self._ensure_item("TEST-COBRO-LIST", 1200)
		self._crear_si(socio.name, item_a, 1200, remarks="Cuota list")
		rows = list_facturas_pendientes_socio(socio.name)
		self.assertTrue(rows)
		self.assertIn("concepto", rows[0])
		self.assertTrue(rows[0]["concepto"])


if __name__ == "__main__":
	import unittest

	unittest.main()
