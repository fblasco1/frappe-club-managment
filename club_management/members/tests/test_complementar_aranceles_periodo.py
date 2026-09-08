"""Tests complementar aranceles período (spec complementar_aranceles_periodo.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cobranza_periodica import (
	complementar_aranceles_periodo_socio,
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestComplementarArancelesPeriodo(MembersTestCase):
	_REFERENCE = "2026-07-01"
	_ITEM_ARANCEL = "TEST-ARANCEL-COMPLEMENTO"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.save(ignore_permissions=True)
		self._ensure_cuota_item()
		self._ensure_arancel_item()

	def _ensure_cuota_item(self) -> None:
		if frappe.db.exists("Item", CUOTA_SOCIAL_ITEM_CODE):
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
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

	def _ensure_arancel_item(self) -> None:
		if frappe.db.exists("Item", self._ITEM_ARANCEL):
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": self._ITEM_ARANCEL,
				"item_name": self._ITEM_ARANCEL,
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 12_500,
			}
		).insert(ignore_permissions=True)

	def _socio_con_inscripcion(self) -> frappe.Document:
		if frappe.db.exists("Actividad", "Actividad Complemento Arancel"):
			actividad = "Actividad Complemento Arancel"
		else:
			actividad = frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": "Actividad Complemento Arancel",
					"habilitada": 1,
					"usa_grupos": 0,
					"item": self._ITEM_ARANCEL,
				}
			).insert(ignore_permissions=True).name

		socio = insert_socio(dni="74001001", email="comp.arancel@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test complemento aranceles")
		inscribir_socio_selecciones(socio.name, [{"actividad": actividad}], activar=False)
		return socio

	def test_complemento_tras_cuota_sin_aranceles(self) -> None:
		socio = self._socio_con_inscripcion()
		cuota_invoice = generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(cuota_invoice)

		arancel_invoice = complementar_aranceles_periodo_socio(
			socio.name,
			reference_date=self._REFERENCE,
		)
		self.assertTrue(arancel_invoice)
		self.assertNotEqual(cuota_invoice, arancel_invoice)

		cuota_doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, cuota_invoice)
		arancel_doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, arancel_invoice)
		cuota_items = {row.item_code for row in cuota_doc.items}
		arancel_items = {row.item_code for row in arancel_doc.items}
		self.assertIn(CUOTA_SOCIAL_ITEM_CODE, cuota_items)
		self.assertNotIn(CUOTA_SOCIAL_ITEM_CODE, arancel_items)
		self.assertIn(self._ITEM_ARANCEL, arancel_items)
		self.assertEqual(
			arancel_doc.get("periodo_cobro") or "",
			format_periodo_cobro(self._REFERENCE),
		)
		self.assertGreater(flt(frappe.db.get_value("Socio", socio.name, "saldo_deuda")), 0)

	def test_idempotencia_complemento_aranceles(self) -> None:
		socio = self._socio_con_inscripcion()
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		first = complementar_aranceles_periodo_socio(socio.name, reference_date=self._REFERENCE)
		second = complementar_aranceles_periodo_socio(socio.name, reference_date=self._REFERENCE)
		self.assertTrue(first)
		self.assertIsNone(second)
