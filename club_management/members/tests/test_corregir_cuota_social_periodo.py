"""Tests corrección de cuota social por enmienda (spec correccion_cuota_social_periodo.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt, today

from club_management.members.data.cuotas_sociales_vigentes import (
	CUOTA_SOCIAL_ITEM_CODE,
	CUOTAS_SOCIALES_ANTERIORES,
	CUOTAS_SOCIALES_VIGENTES,
)
from club_management.members.ops.corregir_cuota_social_periodo import run
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.test_helpers import MembersTestCase, insert_socio

PERIODO = "06/2026"
OTRO_ITEM = "TEST-CORR-CUOTA-OTRO"


class TestValoresCuotaSocialOctubre2026(MembersTestCase):
	def test_valores_vigentes(self) -> None:
		self.assertEqual(
			dict(CUOTAS_SOCIALES_VIGENTES),
			{
				"Activo": 36_000.0,
				"Menor": 33_000.0,
				"2° Hermano": 32_000.0,
				"3° Hermano": 27_500.0,
				"Adherente": 22_000.0,
				"Jubilado": 6_000.0,
			},
		)
		self.assertEqual(dict(CUOTAS_SOCIALES_ANTERIORES)["Activo"], 31_000.0)

	def test_catalogo_informes_incluye_vigentes_y_anteriores(self) -> None:
		from club_management.scripts.bulk_payments import _tarifas_cuota_social_catalogo

		tarifas = _tarifas_cuota_social_catalogo()
		self.assertIn(31_000.0, tarifas)
		self.assertIn(36_000.0, tarifas)


class TestCorregirCuotaSocialPeriodo(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		for code, rate in ((CUOTA_SOCIAL_ITEM_CODE, 31_000), (OTRO_ITEM, 1_000)):
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

	def _factura(self, dni: str, cuota_rate: float) -> tuple[str, str, str]:
		socio = insert_socio(dni=dni, email=f"corr.{dni}@example.com")
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		inv = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": today(),
				"due_date": today(),
				_campo_socio_en(SALES_INVOICE_DOCTYPE): socio.name,
				_campo_periodo_cobro(): PERIODO,
				"remarks": f"Cuota mensual {PERIODO}",
				"items": [
					{"item_code": CUOTA_SOCIAL_ITEM_CODE, "qty": 1, "rate": cuota_rate},
					{"item_code": OTRO_ITEM, "qty": 1, "rate": 1_000},
				],
			}
		)
		inv.insert(ignore_permissions=True)
		inv.submit()
		return inv.name, socio.name, socio.categoria

	def _montos(self, categoria: str) -> tuple[dict[str, float], dict[str, float]]:
		return {categoria: 36_000.0}, {categoria: 31_000.0}

	def _run(self, categoria: str, **kwargs):
		nuevos, anteriores = self._montos(categoria)
		return run(periodo=PERIODO, nuevos=nuevos, anteriores=anteriores, **kwargs)

	def _row(self, report: dict, key: str, factura: str) -> dict | None:
		return next((r for r in report[key] if r["factura"] == factura), None)

	def test_dry_run_detecta_sin_modificar(self) -> None:
		name, _socio, categoria = self._factura("74001001", 31_000)
		report = self._run(categoria)
		row = self._row(report, "a_corregir", name)
		self.assertIsNotNone(row)
		self.assertEqual(row["monto_anterior"], 31_000.0)
		self.assertEqual(row["monto_nuevo"], 36_000.0)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 1)

	def test_apply_protegido(self) -> None:
		name, _socio, categoria = self._factura("74001002", 31_000)
		with self.assertRaises(frappe.ValidationError):
			self._run(categoria, apply=True)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 1)

	def test_apply_enmienda_e_idempotente(self) -> None:
		name, socio, categoria = self._factura("74001003", 31_000)
		total_original = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "grand_total"))

		report = self._run(categoria, apply=True, confirm="local-dev")
		row = self._row(report, "corregidas", name)
		self.assertIsNotNone(row, report)
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 2)

		nueva = frappe.get_doc(SALES_INVOICE_DOCTYPE, row["factura_nueva"])
		self.assertEqual(nueva.docstatus, 1)
		self.assertEqual(nueva.amended_from, name)
		self.assertEqual(nueva.get(_campo_socio_en(SALES_INVOICE_DOCTYPE)), socio)
		self.assertEqual(nueva.get(_campo_periodo_cobro()), PERIODO)
		rates = {r.item_code: flt(r.rate) for r in nueva.items}
		self.assertEqual(rates, {CUOTA_SOCIAL_ITEM_CODE: 36_000.0, OTRO_ITEM: 1_000.0})
		self.assertEqual(flt(nueva.grand_total), total_original + 5_000)

		again = self._run(categoria, apply=True, confirm="local-dev")
		self.assertIsNone(self._row(again, "corregidas", row["factura_nueva"]))
		self.assertIsNotNone(self._row(again, "ya_correctas", row["factura_nueva"]))

	def test_factura_con_pagos_se_respeta(self) -> None:
		name, _socio, categoria = self._factura("74001004", 31_000)
		total = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "grand_total"))
		frappe.db.set_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount", total - 100)
		report = self._run(categoria, apply=True, confirm="local-dev")
		self.assertIsNotNone(self._row(report, "con_pagos", name))
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 1)

	def test_monto_inesperado_va_a_revisar(self) -> None:
		name, _socio, categoria = self._factura("74001005", 29_999)
		report = self._run(categoria, apply=True, confirm="local-dev")
		self.assertIsNotNone(self._row(report, "revisar", name))
		self.assertEqual(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "docstatus"), 1)
