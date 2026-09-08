"""Tests: centro de costo del arancel de actividad.

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.

El arancel de actividad debe imputar al centro de costo de la actividad
(según `Item Default.selling_cost_center`), tanto en la línea de la factura
(`Sales Invoice Item`) como en el asiento (`GL Entry`). El backfill re-etiqueta
las facturas históricas ya emitidas.
"""

from __future__ import annotations

import frappe

from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	_default_company,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cobranza_periodica import (
	complementar_aranceles_periodo_socio,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class _ArancelCostCenterBase(MembersTestCase):
	_REFERENCE = "2026-07-01"
	_ITEM_ARANCEL = "TEST-ARANCEL-CC"
	_CC_NAME = "Test Actividad CC"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.incluir_cargos_extra_en_deuda_mensual = 0
		if not settings.company:
			settings.company = frappe.db.get_value("Company", {}, "name")
		settings.save(ignore_permissions=True)
		self._company = _default_company()
		if not self._company:
			self.skipTest("No hay Company configurada en el sitio")
		self._ensure_cuota_item()
		self._cc = self._ensure_cost_center()
		self._ensure_arancel_item(self._cc)

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

	def _ensure_cost_center(self) -> str:
		parent = frappe.db.get_value(
			"Cost Center", {"company": self._company, "is_group": 1}, "name"
		)
		name = f"{self._CC_NAME} - {frappe.get_cached_value('Company', self._company, 'abbr')}"
		if frappe.db.exists("Cost Center", name):
			return name
		doc = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": self._CC_NAME,
				"company": self._company,
				"is_group": 0,
				"parent_cost_center": parent,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def _ensure_arancel_item(self, cost_center: str) -> None:
		income_account = frappe.get_cached_value("Company", self._company, "default_income_account")
		if frappe.db.exists("Item", self._ITEM_ARANCEL):
			item = frappe.get_doc("Item", self._ITEM_ARANCEL)
		else:
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			item = frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self._ITEM_ARANCEL,
					"item_name": self._ITEM_ARANCEL,
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 12_500,
				}
			)
			item.insert(ignore_permissions=True)
		item.set("item_defaults", [])
		item.append(
			"item_defaults",
			{
				"company": self._company,
				"selling_cost_center": cost_center,
				"income_account": income_account,
			},
		)
		item.save(ignore_permissions=True)

	def _socio_con_inscripcion(self, dni: str = "74009001") -> frappe.Document:
		titulo = "Actividad CC Arancel"
		if frappe.db.exists("Actividad", titulo):
			actividad = titulo
		else:
			actividad = (
				frappe.get_doc(
					{
						"doctype": "Actividad",
						"titulo": titulo,
						"habilitada": 1,
						"usa_grupos": 0,
						"item": self._ITEM_ARANCEL,
					}
				)
				.insert(ignore_permissions=True)
				.name
			)
		socio = insert_socio(dni=dni, email=f"cc.arancel.{dni}@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test CC arancel")
		inscribir_socio_selecciones(socio.name, [{"actividad": actividad}], activar=False)
		return socio

	def _factura_arancel(self, dni: str = "74009001") -> str:
		socio = self._socio_con_inscripcion(dni=dni)
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		arancel_invoice = complementar_aranceles_periodo_socio(
			socio.name, reference_date=self._REFERENCE
		)
		self.assertTrue(arancel_invoice)
		return arancel_invoice


class TestArancelCostCenterForward(_ArancelCostCenterBase):
	def test_linea_arancel_usa_cost_center_actividad(self) -> None:
		invoice = self._factura_arancel(dni="74009011")
		doc = frappe.get_doc("Sales Invoice", invoice)
		fila = next(r for r in doc.items if r.item_code == self._ITEM_ARANCEL)
		self.assertEqual(fila.cost_center, self._cc)

	def test_gl_entry_ingreso_usa_cost_center_actividad(self) -> None:
		invoice = self._factura_arancel(dni="74009012")
		gl = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": invoice, "credit": [">", 0], "is_cancelled": 0},
			fields=["account", "cost_center"],
		)
		self.assertTrue(gl, "El arancel debe generar un asiento de ingreso")
		for row in gl:
			self.assertEqual(row["cost_center"], self._cc)


class TestArancelCostCenterBackfill(_ArancelCostCenterBase):
	def test_backfill_reasigna_cost_center_linea_y_gl(self) -> None:
		from club_management.members.services.cost_center_backfill import (
			reasignar_cost_center_aranceles,
		)

		invoice = self._factura_arancel(dni="74009021")
		# Simula el estado legacy: la línea y el asiento quedaron en el CC por defecto.
		from erpnext import get_default_cost_center

		default_cc = get_default_cost_center(self._company)
		self.assertNotEqual(default_cc, self._cc)
		for row in frappe.get_all(
			"Sales Invoice Item", filters={"parent": invoice, "item_code": self._ITEM_ARANCEL}
		):
			frappe.db.set_value(
				"Sales Invoice Item", row["name"], "cost_center", default_cc, update_modified=False
			)
		frappe.db.sql(
			"update `tabGL Entry` set cost_center=%s where voucher_no=%s and credit>0",
			(default_cc, invoice),
		)

		resultado = reasignar_cost_center_aranceles(invoice_names=[invoice])
		self.assertGreaterEqual(resultado.get("facturas_actualizadas", 0), 1)

		fila_cc = frappe.db.get_value(
			"Sales Invoice Item",
			{"parent": invoice, "item_code": self._ITEM_ARANCEL},
			"cost_center",
		)
		self.assertEqual(fila_cc, self._cc)
		gl = frappe.get_all(
			"GL Entry",
			filters={"voucher_no": invoice, "credit": [">", 0], "is_cancelled": 0},
			fields=["cost_center"],
		)
		self.assertTrue(gl)
		for row in gl:
			self.assertEqual(row["cost_center"], self._cc)
