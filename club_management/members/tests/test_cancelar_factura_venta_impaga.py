"""Tests: cancelar Sales Invoice impaga y regenerar cargo.

Spec: `club_management/specs/cancelar_factura_venta_impaga.md`
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	generar_cargo_socio,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestCancelarFacturaVentaImpaga(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.cancel.impaga@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		settings.save(ignore_permissions=True)
		self._REFERENCE = "2026-07-01"

	def _socio_activo(self, *, dni: str, email: str):
		socio = insert_socio(dni=dni, email=email)
		cambiar_estado(socio.name, "Activo", motivo="Test cancel SI impaga")
		return socio

	def test_cancelar_factura_impaga_actualiza_saldo(self) -> None:
		from club_management.members.services.cobranza_manual import cancelar_factura_venta_impaga

		socio = self._socio_activo(dni="99003001", email="cancel.impaga.ok@example.com")
		invoice_name = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
		saldo_antes = sync_saldo_deuda_socio(socio.name)
		self.assertGreater(saldo_antes, 0)

		frappe.set_user(self._secretaria)
		try:
			result = cancelar_factura_venta_impaga(socio.name, invoice_name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(result["status"], "ok")
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "docstatus"), 2)
		self.assertEqual(flt(frappe.db.get_value("Socio", socio.name, "saldo_deuda")), 0)

	def test_no_cancelar_factura_cobrada(self) -> None:
		from club_management.members.services.cobranza_manual import cancelar_factura_venta_impaga

		socio = self._socio_activo(dni="99003002", email="cancel.impaga.paid@example.com")
		invoice_name = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
		registrar_cobro_manual(socio.name, invoice_name)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cancelar_factura_venta_impaga(socio.name, invoice_name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "docstatus"), 1)

	def test_no_cancelar_factura_de_otro_socio(self) -> None:
		from club_management.members.services.cobranza_manual import cancelar_factura_venta_impaga

		socio_a = self._socio_activo(dni="99003003", email="cancel.impaga.a@example.com")
		socio_b = self._socio_activo(dni="99003004", email="cancel.impaga.b@example.com")
		invoice_name = generar_cargo_socio(socio_a.name, reference_date=self._REFERENCE)

		frappe.set_user(self._secretaria)
		try:
			with self.assertRaises(frappe.ValidationError):
				cancelar_factura_venta_impaga(socio_b.name, invoice_name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "docstatus"), 1)

	def test_regenerar_cargo_tras_cancelar(self) -> None:
		from club_management.members.services.cobranza_manual import cancelar_factura_venta_impaga

		socio = self._socio_activo(dni="99003005", email="cancel.impaga.regen@example.com")
		primera = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
		periodo = format_periodo_cobro(self._REFERENCE)
		campo_periodo = _campo_periodo_cobro()
		if campo_periodo:
			self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, primera, campo_periodo), periodo)

		frappe.set_user(self._secretaria)
		try:
			cancelar_factura_venta_impaga(socio.name, primera)
			segunda = generar_cargo_socio(socio.name, reference_date=self._REFERENCE)
		finally:
			frappe.set_user("Administrator")

		self.assertNotEqual(primera, segunda)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, segunda, "docstatus"), 1)
		if campo_periodo:
			self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, segunda, campo_periodo), periodo)
		campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		if campo_socio:
			self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, segunda, campo_socio), socio.name)


if __name__ == "__main__":
	import unittest

	unittest.main()
