"""Tests generación mensual de deuda (spec cobranza_periodica_mensual.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate

from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cobranza_periodica import (
	es_dia_generacion_deuda,
	factura_periodo_existe,
	format_periodo_cobro,
	generar_deuda_mensual_socio,
	generar_deuda_mensual_socios,
	primer_vencimiento,
	resolve_fechas_factura_mensual,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCobranzaPeriodicaMensual(MembersTestCase):
	_REFERENCE = "2026-06-01"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._ensure_club_settings()
		self._ensure_cuota_item()

	def _ensure_club_settings(self) -> None:
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.dia_generacion_deuda = 1
		settings.dia_primer_vencimiento = 10
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.incluir_aranceles_en_deuda_mensual = 1
		settings.incluir_cargos_extra_en_deuda_mensual = 1
		settings.save(ignore_permissions=True)

	def _ensure_cuota_item(self) -> None:
		if not frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
			item_group = (
				frappe.db.get_value("Item Group", {"name": ["like", "ICDPE%"]}, "name")
				or frappe.db.get_value("Item Group", {}, "name")
				or "All Item Groups"
			)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": CUOTA_SOCIAL_ITEM_CODE,
					"item_name": "Cuota Social Base",
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 29_000,
				}
			).insert(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test cobranza periódica")
		return socio

	def _campo_socio_si(self) -> str:
		for fieldname in ("socio", "custom_socio"):
			if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field(fieldname):
				return fieldname
		self.fail("Sales Invoice sin campo Socio")

	def test_es_dia_generacion_deuda(self) -> None:
		self.assertTrue(es_dia_generacion_deuda(self._REFERENCE))
		self.assertFalse(es_dia_generacion_deuda("2026-06-15"))

	def test_primer_vencimiento_mismo_mes(self) -> None:
		self.assertEqual(primer_vencimiento(self._REFERENCE, 10), getdate("2026-06-10"))

	def test_resolve_fechas_generacion_tardia_ajusta_due(self) -> None:
		settings = frappe.get_single("Club Settings")
		posting, due = resolve_fechas_factura_mensual(
			self._REFERENCE,
			int(settings.dia_primer_vencimiento or 10),
		)
		self.assertGreaterEqual(due, posting)

	def test_genera_factura_socio_activo(self) -> None:
		socio = self._socio_activo(dni="73001001", email="deuda.mensual@example.com")
		settings = frappe.get_single("Club Settings")
		posting, due = resolve_fechas_factura_mensual(
			self._REFERENCE,
			int(settings.dia_primer_vencimiento or 10),
		)
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(invoice_name)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		self.assertEqual(invoice.docstatus, 1)
		self.assertEqual(str(invoice.posting_date), str(posting))
		self.assertEqual(str(invoice.due_date), str(due))
		campo_socio = self._campo_socio_si()
		self.assertEqual(invoice.get(campo_socio), socio.name)
		self.assertTrue(any(row.item_code == CUOTA_SOCIAL_ITEM_CODE for row in invoice.items))

	def test_idempotencia_mismo_periodo(self) -> None:
		socio = self._socio_activo(dni="73001002", email="deuda.idem@example.com")
		periodo = format_periodo_cobro(self._REFERENCE)
		first = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		second = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(first)
		self.assertIsNone(second)
		self.assertTrue(factura_periodo_existe(socio.name, periodo))
		campo_socio = self._campo_socio_si()
		count = frappe.db.count(
			SALES_INVOICE_DOCTYPE,
			{campo_socio: socio.name, "docstatus": 1},
		)
		self.assertEqual(count, 1)

	def test_crea_customer_si_falta(self) -> None:
		socio = self._socio_activo(dni="73001003", email="deuda.customer@example.com")
		customer_field = None
		for field in ("socio", "custom_socio"):
			if frappe.get_meta("Customer").has_field(field):
				customer_field = field
				for name in frappe.get_all("Customer", filters={field: socio.name}, pluck="name"):
					frappe.delete_doc("Customer", name, force=True)
		self.assertIsNotNone(customer_field)
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(invoice_name)
		self.assertTrue(frappe.db.exists("Customer", {customer_field: socio.name}))

	def test_excluye_vitalicio_en_job_masivo(self) -> None:
		socio = self._socio_activo(dni="73001004", email="deuda.vital@example.com")
		frappe.db.set_value("Socio", socio.name, "categoria", "Vitalicio")
		result = generar_deuda_mensual_socios(reference_date=self._REFERENCE)
		self.assertNotIn(socio.name, result.get("invoice_names", []))

	def test_incluye_arancel_inscripcion_activa(self) -> None:
		item_code = "TEST-ARANCEL-PERIODICO"
		if not frappe.db.exists("Item", item_code):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 7500,
				}
			).insert(ignore_permissions=True)

		if frappe.db.exists("Actividad", "Zumba Periodico"):
			actividad = "Zumba Periodico"
		else:
			actividad = frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": "Zumba Periodico",
					"habilitada": 1,
					"usa_grupos": 0,
					"item": item_code,
				}
			).insert(ignore_permissions=True).name

		socio = self._socio_activo(dni="73001005", email="deuda.arancel@example.com")
		inscribir_socio_selecciones(socio.name, [{"actividad": actividad}], activar=False)
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(invoice_name)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		item_codes = {row.item_code for row in invoice.items}
		self.assertIn(item_code, item_codes)

	def test_sincroniza_saldo_deuda(self) -> None:
		socio = self._socio_activo(dni="73001006", email="deuda.saldo@example.com")
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		saldo = flt(frappe.db.get_value("Socio", socio.name, "saldo_deuda"))
		self.assertGreater(saldo, 0)
