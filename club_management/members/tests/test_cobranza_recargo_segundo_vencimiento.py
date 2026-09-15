"""Tests recargo al segundo vencimiento (spec cobranza_recargo_segundo_vencimiento.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_periodica import (
	es_dia_segundo_vencimiento,
	format_periodo_cobro,
	generar_deuda_mensual_socio,
	periodo_recargo,
	segundo_vencimiento,
)
from club_management.members.services.cobranza_recargo import (
	aplicar_recargo_factura_mensual,
	aplicar_recargos_segundo_vencimiento,
	calcular_monto_recargo,
	recargo_periodo_existe,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCobranzaRecargoSegundoVencimiento(MembersTestCase):
	_GEN = "2026-06-01"
	_SEGUNDO = "2026-06-30"
	_ITEM_RECARGO = "TEST-ITEM-RECARGO-MORA"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._ensure_settings()

	def _ensure_settings(self) -> None:
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		settings.dia_segundo_vencimiento = "Ultimo dia del mes"
		settings.recargo_segundo_vencimiento_pct = 10
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		if not frappe.db.exists("Item", self._ITEM_RECARGO):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self._ITEM_RECARGO,
					"item_name": "Recargo mora test",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 0,
				}
			).insert(ignore_permissions=True)
		settings.item_recargo_mora = self._ITEM_RECARGO
		settings.save(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test recargo")
		return socio

	def _factura_mensual(self, socio_name: str) -> str:
		name = generar_deuda_mensual_socio(socio_name, reference_date=self._GEN)
		self.assertTrue(name)
		return name

	def test_segundo_vencimiento_ultimo_dia_mes(self) -> None:
		self.assertEqual(
			segundo_vencimiento(self._GEN, "Ultimo dia del mes").isoformat(),
			"2026-06-30",
		)
		self.assertTrue(es_dia_segundo_vencimiento(self._SEGUNDO))

	def test_calcular_recargo_pago_parcial(self) -> None:
		self.assertEqual(calcular_monto_recargo(5000, 10), 500.0)

	def test_aplica_recargo_en_segundo_vencimiento(self) -> None:
		socio = self._socio_activo(dni="75001001", email="recargo@example.com")
		invoice_name = self._factura_mensual(socio.name)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		saldo = flt(invoice.outstanding_amount)

		recargo_name = aplicar_recargo_factura_mensual(
			invoice_name, reference_date=self._SEGUNDO
		)
		self.assertTrue(recargo_name)
		recargo = frappe.get_doc(SALES_INVOICE_DOCTYPE, recargo_name)
		self.assertEqual(recargo.docstatus, 1)
		self.assertEqual(flt(recargo.grand_total), calcular_monto_recargo(saldo, 10))
		periodo = format_periodo_cobro(self._GEN)
		self.assertTrue(recargo_periodo_existe(socio.name, periodo))
		self.assertGreater(sync_saldo_deuda_socio(socio.name), saldo)

	def test_no_recargo_si_factura_pagada(self) -> None:
		socio = self._socio_activo(dni="75001002", email="recargo.pagado@example.com")
		invoice_name = self._factura_mensual(socio.name)
		registrar_cobro_manual(socio.name, invoice_name)

		recargo_name = aplicar_recargo_factura_mensual(
			invoice_name, reference_date=self._SEGUNDO
		)
		self.assertIsNone(recargo_name)

	def test_idempotencia_recargo_mismo_periodo(self) -> None:
		socio = self._socio_activo(dni="75001003", email="recargo.idem@example.com")
		invoice_name = self._factura_mensual(socio.name)
		first = aplicar_recargo_factura_mensual(invoice_name, reference_date=self._SEGUNDO)
		second = aplicar_recargo_factura_mensual(invoice_name, reference_date=self._SEGUNDO)
		self.assertTrue(first)
		self.assertIsNone(second)

	def test_batch_omite_sin_item_recargo(self) -> None:
		socio = self._socio_activo(dni="75001004", email="recargo.noitem@example.com")
		self._factura_mensual(socio.name)
		settings = frappe.get_single("Club Settings")
		settings.item_recargo_mora = ""
		settings.save(ignore_permissions=True)

		result = aplicar_recargos_segundo_vencimiento(reference_date=self._SEGUNDO)
		self.assertGreater(result["errores"], 0)
		self.assertEqual(result["recargos_creados"], 0)

	def test_periodo_recargo_suffix(self) -> None:
		self.assertEqual(periodo_recargo("06/2026"), "06/2026-REC")
