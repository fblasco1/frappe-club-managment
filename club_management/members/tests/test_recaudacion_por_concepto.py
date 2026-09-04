"""Tests: informe Recaudación por concepto.

Spec: `club_management/specs/informe_rendicion_cobranza_secretaria.md` (fase 2)
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
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.recaudacion_por_concepto import (
	VISTA_PAGOS_DIA,
	get_informe_recaudacion_por_concepto,
	get_recaudacion_por_concepto_report_data,
	get_recaudacion_por_concepto_report_summary,
	get_recaudacion_unificada_report_columns,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestRecaudacionPorConcepto(MembersTestCase):
	_DESDE = "2020-04-01"
	_HASTA = "2020-04-30"
	_DIA_COBRO = "2020-04-15"
	_PERIODO = "04/2020"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.rec.concepto@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)

	def _ensure_item(self, code: str, rate: float, *, item_name: str | None = None) -> str:
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": item_name or code,
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "Products",
					"stock_uom": "Nos",
					"is_sales_item": 1,
					"is_stock_item": 0,
					"standard_rate": rate,
				}
			).insert(ignore_permissions=True)
		return code

	def _crear_si(
		self,
		socio_name: str,
		item_code: str,
		rate: float,
		*,
		description: str,
	) -> str:
		from club_management.members.services.cobranza_manual import (
			_default_company,
			ensure_customer_for_socio,
		)

		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		customer = ensure_customer_for_socio(socio_name)
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": customer,
			"company": _default_company(),
			"posting_date": self._DIA_COBRO,
			"due_date": self._DIA_COBRO,
			"set_posting_time": 1,
			campo: socio_name,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": rate,
					"description": description,
				}
			],
		}
		if campo_periodo:
			payload[campo_periodo] = self._PERIODO
		doc = frappe.get_doc(payload)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_reporte_en_listado_gestion_socios(self) -> None:
		self.assertIn("Cobranza por fechas", CLUB_DESK_REPORTS)
		self.assertNotIn("Recaudacion por concepto", CLUB_DESK_REPORTS)
		self.assertNotIn("Pagos del dia", CLUB_DESK_REPORTS)

	def test_vista_pagos_del_dia_usa_columnas_diarias(self) -> None:
		rendicion_cols = get_recaudacion_unificada_report_columns({"vista": "Rendición por concepto"})
		pagos_cols = get_recaudacion_unificada_report_columns({"vista": VISTA_PAGOS_DIA})
		self.assertEqual(rendicion_cols[0]["fieldname"], "concepto_informe")
		self.assertEqual(pagos_cols[0]["fieldname"], "socio_label")

	def test_recaudacion_por_concepto_informe_y_totales(self) -> None:
		socio = insert_socio(
			dni="99440001",
			email="rec.concepto@example.com",
			categoria="Activo",
		)
		cambiar_estado(socio.name, "Activo", motivo="Test recaudación concepto")
		item_cuota = self._ensure_item("ICDPE-CUOTA-SOCIAL", 31000)
		item_arancel = self._ensure_item("ICDPE-BASQUET-ESCUELITA", 24150, item_name="Básquet Escuelita")
		si_c = self._crear_si(
			socio.name,
			item_cuota,
			31000,
			description="Cuota Social Activo 04/2020",
		)
		si_a = self._crear_si(
			socio.name,
			item_arancel,
			24150,
			description="Adicional Basquet Escuelita",
		)
		sync_saldo_deuda_socio(socio.name)
		total_c = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_c, "outstanding_amount"))
		total_a = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_a, "outstanding_amount"))

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_manual(
				socio.name,
				si_c,
				mode_of_payment="Cash",
				posting_date=self._DIA_COBRO,
			)
			registrar_cobro_manual(
				socio.name,
				si_a,
				mode_of_payment="Wire Transfer",
				posting_date=self._DIA_COBRO,
			)
			filters = {"fecha_desde": self._DESDE, "fecha_hasta": self._HASTA}
			informe = get_informe_recaudacion_por_concepto(filters)
			summary = get_recaudacion_por_concepto_report_summary(filters)
			data = get_recaudacion_por_concepto_report_data(filters)
		finally:
			frappe.set_user("Administrator")

		self.assertAlmostEqual(flt(informe["total"]), total_c + total_a)
		por_concepto = {row["concepto"]: flt(row["total"]) for row in informe["por_concepto"]}
		self.assertAlmostEqual(por_concepto.get("Cuota Social Activo", 0), total_c)
		self.assertAlmostEqual(por_concepto.get("Adicional Basquet Escuelita", 0), total_a)
		self.assertAlmostEqual(
			sum(flt(row["total"]) for row in informe["por_concepto"]),
			flt(informe["total"]),
		)

		conceptos_linea = {row["concepto_informe"] for row in informe["lineas"]}
		self.assertIn("Cuota Social Activo", conceptos_linea)
		self.assertIn("Adicional Basquet Escuelita", conceptos_linea)

		summary_labels = [row["label"] for row in summary]
		self.assertEqual(summary_labels[0], "Total recaudado")
		self.assertTrue(
			any("Total Cuota Social Activo" in str(row.get("concepto_informe") or "") for row in data)
		)

	def test_filtro_solo_cuotas_sociales(self) -> None:
		socio = insert_socio(dni="99440002", email="rec.solo.cuota@example.com", categoria="Menor")
		cambiar_estado(socio.name, "Activo", motivo="Test solo cuota")
		item_cuota = self._ensure_item("ICDPE-CUOTA-SOCIAL-MENOR-TEST", 28500)
		item_arancel = self._ensure_item("ICDPE-TEST-ARANCEL-REC", 5000)
		si_c = self._crear_si(socio.name, item_cuota, 28500, description="Cuota Social Menor")
		si_a = self._crear_si(socio.name, item_arancel, 5000, description="Arancel test")
		sync_saldo_deuda_socio(socio.name)
		total_c = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, si_c, "outstanding_amount"))

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_manual(
				socio.name,
				si_c,
				mode_of_payment="Cash",
				posting_date=self._DIA_COBRO,
			)
			registrar_cobro_manual(
				socio.name,
				si_a,
				mode_of_payment="Cash",
				posting_date=self._DIA_COBRO,
			)
			informe = get_informe_recaudacion_por_concepto(
				{
					"fecha_desde": self._DESDE,
					"fecha_hasta": self._HASTA,
					"solo_cuotas_sociales": 1,
				}
			)
		finally:
			frappe.set_user("Administrator")

		self.assertAlmostEqual(flt(informe["total"]), total_c)
		conceptos = {row["concepto_informe"] for row in informe["lineas"]}
		self.assertIn("Cuota Social Menor", conceptos)
		self.assertFalse(any("Arancel" in c for c in conceptos))

	def test_si_mixta_imputa_por_concepto_pe_no_prorratea(self) -> None:
		from club_management.members.services.cobranza_manual import (
			_campo_periodo_cobro,
			_default_company,
			ensure_customer_for_socio,
			registrar_cobro_parcial_factura,
		)

		socio = insert_socio(dni="99440004", email="rec.mixta@example.com", categoria="Menor")
		cambiar_estado(socio.name, "Activo", motivo="Test SI mixta recaudación")
		item_cuota = self._ensure_item("ICDPE-CUOTA-SOCIAL", 28500)
		item_arancel = self._ensure_item("ICDPE-VOLEY-FEDERADO", 24150, item_name="Voley federado")
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		campo_periodo = _campo_periodo_cobro()
		payload: dict = {
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": ensure_customer_for_socio(socio.name),
			"company": _default_company(),
			"posting_date": self._DIA_COBRO,
			"due_date": self._DIA_COBRO,
			"set_posting_time": 1,
			campo: socio.name,
			"items": [
				{"item_code": item_cuota, "qty": 1, "rate": 28500, "description": "Cuota social"},
				{"item_code": item_arancel, "qty": 1, "rate": 24150, "description": "Adicional Voley Menor"},
			],
		}
		if campo_periodo:
			payload[campo_periodo] = self._PERIODO
		invoice = frappe.get_doc(payload)
		invoice.insert(ignore_permissions=True)
		invoice.submit()

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_parcial_factura(
				socio.name,
				invoice.name,
				28500,
				mode_of_payment="Cash",
				posting_date=self._DIA_COBRO,
				reference_no="INF-1-99440004-04/2020-28500.0-Cuota Social Menor",
			)
			informe = get_informe_recaudacion_por_concepto(
				{"fecha_desde": self._DESDE, "fecha_hasta": self._HASTA}
			)
		finally:
			frappe.set_user("Administrator")

		por_concepto = {row["concepto"]: flt(row["total"]) for row in informe["por_concepto"]}
		self.assertAlmostEqual(por_concepto.get("Cuota Social Menor", 0), 28500.0)
		self.assertAlmostEqual(por_concepto.get("Adicional Voley Menor", 0), 0.0)

	def test_filtro_periodo_cobro(self) -> None:
		socio = insert_socio(dni="99440003", email="rec.periodo@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test período")
		item = self._ensure_item("ICDPE-CUOTA-SOCIAL-PER", 1000)
		si = self._crear_si(socio.name, item, 1000, description="Cuota social")
		sync_saldo_deuda_socio(socio.name)

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_manual(
				socio.name,
				si,
				mode_of_payment="Cash",
				posting_date=self._DIA_COBRO,
			)
			ok = get_informe_recaudacion_por_concepto(
				{
					"fecha_desde": self._DESDE,
					"fecha_hasta": self._HASTA,
					"periodo_cobro": self._PERIODO,
				}
			)
			vacio = get_informe_recaudacion_por_concepto(
				{
					"fecha_desde": self._DESDE,
					"fecha_hasta": self._HASTA,
					"periodo_cobro": format_periodo_cobro("2020-05-01"),
				}
			)
		finally:
			frappe.set_user("Administrator")

		self.assertAlmostEqual(flt(ok["total"]), 1000.0)
		self.assertAlmostEqual(flt(vacio["total"]), 0.0)
