"""Tests informe Deuda cuotas sociales (spec deuda_cuotas_sociales.md)."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import flt, today

from club_management.members.data.cuotas_sociales_vigentes import (
	CUOTA_SOCIAL_ITEM_CODE,
	CUOTA_SOCIAL_LEGACY_ITEM_CODE,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.deuda_cuotas_sociales import get_deuda_cuotas_sociales
from club_management.members.test_helpers import MembersTestCase, insert_socio

OTRO_ITEM = "TEST-DEUDA-CUOTA-ARANCEL"
IMPUTACION = "club_management.members.services.deuda_cuotas_sociales._cobros_imputados_por_linea"


class TestDeudaCuotasSociales(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		for code, rate in ((CUOTA_SOCIAL_ITEM_CODE, 36_000), (OTRO_ITEM, 20_000)):
			if not frappe.db.exists("Item", code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": code,
						"item_name": code,
						"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
						or "All Item Groups",
						"is_stock_item": 0,
						"is_sales_item": 1,
						"standard_rate": rate,
					}
				).insert(ignore_permissions=True)

	def _socio(self, dni: str, **kwargs):
		return insert_socio(dni=dni, email=f"deuda.cs.{dni}@example.com", **kwargs)

	def _factura(self, socio, periodo: str, items: list[tuple[str, float]]) -> str:
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		inv = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": today(),
				"due_date": today(),
				_campo_socio_en(SALES_INVOICE_DOCTYPE): socio.name,
				_campo_periodo_cobro(): periodo,
				"items": [{"item_code": code, "qty": 1, "rate": rate} for code, rate in items],
			}
		)
		inv.insert(ignore_permissions=True)
		inv.submit()
		return inv.name

	def _fila(self, data: list[dict], socio: str) -> dict | None:
		return next((row for row in data if row.get("socio") == socio), None)

	def test_fila_por_socio_con_periodos_ordenados(self) -> None:
		socio = self._socio("75001001")
		self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000)])
		self._factura(socio, "09/2026", [(CUOTA_SOCIAL_ITEM_CODE, 31_000)])

		_columns, data, _msg, _chart, summary = get_deuda_cuotas_sociales({})
		fila = self._fila(data, socio.name)
		self.assertIsNotNone(fila)
		self.assertEqual(fila["periodos"], "09/2026, 10/2026")
		self.assertEqual(fila["cantidad_periodos"], 2)
		self.assertEqual(flt(fila["deuda"]), 67_000.0)
		labels = {row["label"] for row in summary}
		self.assertTrue({"Socios con deuda", "Períodos adeudados", "Total adeudado"} <= labels)

	def test_solo_cuenta_linea_cuota_social(self) -> None:
		socio = self._socio("75001002")
		self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000), (OTRO_ITEM, 20_000)])
		_columns, data, *_rest = get_deuda_cuotas_sociales({})
		self.assertEqual(flt(self._fila(data, socio.name)["deuda"]), 36_000.0)

	def test_item_legado_cuenta_como_cuota_social(self) -> None:
		if not frappe.db.exists("Item", CUOTA_SOCIAL_LEGACY_ITEM_CODE):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": CUOTA_SOCIAL_LEGACY_ITEM_CODE,
					"item_name": CUOTA_SOCIAL_LEGACY_ITEM_CODE,
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "All Item Groups",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 31_000,
				}
			).insert(ignore_permissions=True)
		socio = self._socio("75001009")
		self._factura(socio, "09/2026", [(CUOTA_SOCIAL_LEGACY_ITEM_CODE, 31_000), (OTRO_ITEM, 20_000)])
		_columns, data, *_rest = get_deuda_cuotas_sociales(
			{"periodo_desde": "09/2026", "periodo_hasta": "09/2026"}
		)
		fila = self._fila(data, socio.name)
		self.assertIsNotNone(fila)
		self.assertEqual(flt(fila["deuda"]), 31_000.0)

	def test_socio_sin_deuda_de_cuota_no_aparece(self) -> None:
		socio = self._socio("75001003")
		self._factura(socio, "10/2026", [(OTRO_ITEM, 20_000)])
		_columns, data, *_rest = get_deuda_cuotas_sociales({})
		self.assertIsNone(self._fila(data, socio.name))

	def test_cobro_parcial_imputado_al_arancel_mantiene_cuota(self) -> None:
		socio = self._socio("75001004")
		name = self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000), (OTRO_ITEM, 20_000)])
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount", 36_000)
		imputado = [
			{"item_code": CUOTA_SOCIAL_ITEM_CODE, "restante": 36_000.0},
			{"item_code": OTRO_ITEM, "restante": 0.0},
		]
		with patch(IMPUTACION, return_value=imputado) as mocked:
			_columns, data, *_rest = get_deuda_cuotas_sociales({})
		mocked.assert_any_call(name)
		self.assertEqual(flt(self._fila(data, socio.name)["deuda"]), 36_000.0)

	def test_cuota_pagada_no_cuenta_el_periodo(self) -> None:
		socio = self._socio("75001005")
		name = self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000), (OTRO_ITEM, 20_000)])
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount", 20_000)
		imputado = [
			{"item_code": CUOTA_SOCIAL_ITEM_CODE, "restante": 0.0},
			{"item_code": OTRO_ITEM, "restante": 20_000.0},
		]
		with patch(IMPUTACION, return_value=imputado):
			_columns, data, *_rest = get_deuda_cuotas_sociales({})
		self.assertIsNone(self._fila(data, socio.name))

	def test_filtro_periodo_desde_hasta(self) -> None:
		socio = self._socio("75001006")
		self._factura(socio, "08/2026", [(CUOTA_SOCIAL_ITEM_CODE, 31_000)])
		self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000)])
		_columns, data, *_rest = get_deuda_cuotas_sociales(
			{"periodo_desde": "09/2026", "periodo_hasta": "12/2026"}
		)
		fila = self._fila(data, socio.name)
		self.assertEqual(fila["periodos"], "10/2026")
		self.assertEqual(flt(fila["deuda"]), 36_000.0)

	def test_filtro_categoria(self) -> None:
		socio = self._socio("75001007")
		self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000)])
		otra = "__categoria_inexistente__"
		_columns, data, *_rest = get_deuda_cuotas_sociales({"categoria": otra})
		self.assertIsNone(self._fila(data, socio.name))
		_columns, data, *_rest = get_deuda_cuotas_sociales({"categoria": socio.categoria})
		self.assertIsNotNone(self._fila(data, socio.name))

	def test_baja_solo_si_se_filtra_por_estado(self) -> None:
		socio = self._socio("75001008")
		self._factura(socio, "10/2026", [(CUOTA_SOCIAL_ITEM_CODE, 36_000)])
		frappe.db.set_value("Socio", socio.name, "estado", "Baja")
		_columns, data, *_rest = get_deuda_cuotas_sociales({})
		self.assertIsNone(self._fila(data, socio.name))
		_columns, data, *_rest = get_deuda_cuotas_sociales({"estado": "Baja"})
		self.assertIsNotNone(self._fila(data, socio.name))

	def test_report_restringido_a_secretaria(self) -> None:
		roles = set(frappe.get_all("Has Role", filters={"parent": "Deuda cuotas sociales"}, pluck="role"))
		self.assertEqual(roles, {"Secretaria", "System Manager"})
