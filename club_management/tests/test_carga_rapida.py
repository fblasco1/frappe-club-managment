"""Tests carga rápida ingreso/egreso."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, flt, today

from club_management.finance.services.carga_rapida import (
	erpnext_finance_disponible,
	registrar_egreso,
	registrar_ingreso,
)
from club_management.finance.setup.seed_finance_masters import run_seed_finance_masters
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.tests.test_rol_tesoreria import make_tesoreria_user


class TestCargaRapida(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_finance_disponible():
			self.skipTest("ERPNext no instalado")
		try:
			self.company = resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		run_seed_finance_masters()
		self.secretaria = make_secretaria_user("secretaria.finanzas@example.com")

	def _require_item(self, code: str) -> None:
		if not frappe.db.exists("Item", code):
			self.skipTest(f"Ítem {code} no sembrado (cuentas/CC faltantes)")

	def _require_supplier(self, name: str) -> str:
		# Puede haberse creado con otro name; buscar por supplier_name
		if frappe.db.exists("Supplier", name):
			return name
		found = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
		if found:
			return found
		self.skipTest(f"Supplier {name} no sembrado")

	def test_registrar_egreso_crea_purchase_invoice(self) -> None:
		self._require_item("ICDPE-FIN-SUELDOS")
		supplier = self._require_supplier("ICDPE-Sueldos Personal")
		due = add_days(today(), 3)

		frappe.set_user(self.secretaria)
		try:
			result = registrar_egreso(
				supplier=supplier,
				item_code="ICDPE-FIN-SUELDOS",
				amount=1000,
				due_date=due,
				club_concepto="Personal",
			)
		finally:
			frappe.set_user("Administrator")

		pi = result["purchase_invoice"]
		self.assertTrue(pi)
		self.assertEqual(frappe.db.get_value("Purchase Invoice", pi, "docstatus"), 1)
		self.assertEqual(flt(frappe.db.get_value("Purchase Invoice", pi, "outstanding_amount")), 1000)
		if frappe.get_meta("Purchase Invoice").has_field("club_concepto"):
			self.assertEqual(frappe.db.get_value("Purchase Invoice", pi, "club_concepto"), "Personal")

	def test_egreso_pagado_ahora_crea_payment_entry(self) -> None:
		self._require_item("ICDPE-FIN-LUZ")
		supplier = self._require_supplier("ICDPE-Servicios Publicos")
		if not frappe.db.exists("Mode of Payment", "Cash"):
			self.skipTest("Mode of Payment Cash no configurado")

		frappe.set_user(self.secretaria)
		try:
			result = registrar_egreso(
				supplier=supplier,
				item_code="ICDPE-FIN-LUZ",
				amount=500,
				due_date=today(),
				club_concepto="Estructura",
				pagado_ahora=True,
				mode_of_payment="Cash",
			)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(result["payment_entry"])
		self.assertEqual(
			flt(frappe.db.get_value("Purchase Invoice", result["purchase_invoice"], "outstanding_amount")),
			0,
		)

	def test_registrar_ingreso_crea_sales_invoice(self) -> None:
		self._require_item("ICDPE-FIN-ENTRADAS")

		frappe.set_user(self.secretaria)
		try:
			result = registrar_ingreso(
				item_code="ICDPE-FIN-ENTRADAS",
				amount=2500,
				club_concepto="Deportiva",
			)
		finally:
			frappe.set_user("Administrator")

		si = result["sales_invoice"]
		self.assertTrue(si)
		self.assertEqual(frappe.db.get_value("Sales Invoice", si, "docstatus"), 1)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", si, "outstanding_amount")), 2500)

	def test_concepto_invalido_falla(self) -> None:
		self._require_item("ICDPE-FIN-SUELDOS")
		supplier = self._require_supplier("ICDPE-Sueldos Personal")
		frappe.set_user(self.secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				registrar_egreso(
					supplier=supplier,
					item_code="ICDPE-FIN-SUELDOS",
					amount=100,
					due_date=today(),
					club_concepto="Inventado",
				)
		finally:
			frappe.set_user("Administrator")

	def test_tesoreria_no_puede_cargar(self) -> None:
		self._require_item("ICDPE-FIN-ENTRADAS")
		user = make_tesoreria_user("tesoreria.nocarga2@example.com")
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				registrar_ingreso(item_code="ICDPE-FIN-ENTRADAS", amount=100)
		finally:
			frappe.set_user("Administrator")
