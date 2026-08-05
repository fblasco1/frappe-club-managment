"""Tests prepago / cancelación adelantada de cargos extras.

Spec: `club_management/specs/cargo_extra_prepago_adelantado.md`
"""

from __future__ import annotations

import frappe
from frappe.exceptions import ValidationError
from frappe.utils import flt

from club_management.members.services.cargo_extra_prepago import (
	list_meses_prepago_cargo,
	prepagar_cargo_socio,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	item_codes_facturados_en_periodo,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCargoExtraPrepago(MembersTestCase):
	_ITEM = "TEST-CARGO-PREPAGO"
	_HOY = "2026-07-15"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._ensure_item()
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		settings.incluir_cargos_extra_en_deuda_mensual = 1
		settings.incluir_aranceles_en_deuda_mensual = 0
		icdpe = frappe.db.get_value("Company", {"name": ["like", "%Pedro%"]}, "name")
		if icdpe:
			settings.company = icdpe
		elif not settings.company:
			settings.company = frappe.db.get_value("Company", {}, "name")
		for row in settings.cuotas_categoria or []:
			if row.categoria == "Activo":
				row.monto = 1000
		settings.save(ignore_permissions=True)

	def _ensure_item(self) -> None:
		if frappe.db.exists("Item", self._ITEM):
			frappe.db.set_value("Item", self._ITEM, "standard_rate", 5000)
			return
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": self._ITEM,
				"item_name": self._ITEM,
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": 5000,
			}
		).insert(ignore_permissions=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test prepago cargo")
		return socio

	def _crear_recurrente(self, socio_name: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Cargo Socio",
				"socio": socio_name,
				"titulo": "Cuota Federativa Prepago",
				"tipo_cargo": "Cuota Federativa",
				"modo_cobro": "Recurrente",
				"item": self._ITEM,
				"monto": 5000,
				"fecha_desde": "2026-03-01",
				"fecha_hasta": "2026-12-31",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_list_meses_restantes_desde_hoy(self) -> None:
		socio = self._socio_activo(dni="78001001", email="prepago.list@example.com")
		cargo = self._crear_recurrente(socio.name)
		meses = list_meses_prepago_cargo(cargo, reference_date=self._HOY)
		periodos = [m["periodo"] for m in meses]
		self.assertIn("07/2026", periodos)
		self.assertIn("12/2026", periodos)
		self.assertNotIn("02/2026", periodos)
		self.assertNotIn("06/2026", periodos)

	def test_prepagar_meses_futuros(self) -> None:
		socio = self._socio_activo(dni="78001002", email="prepago.crear@example.com")
		cargo = self._crear_recurrente(socio.name)
		result = prepagar_cargo_socio(
			cargo,
			periodos=["08/2026", "09/2026"],
			reference_date=self._HOY,
		)
		self.assertEqual(len(result["sales_invoices"]), 2)
		campo = _campo_periodo_cobro()
		periodos = {
			frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, campo)
			for name in result["sales_invoices"]
		}
		self.assertEqual(periodos, {"08/2026", "09/2026"})
		self.assertIn(self._ITEM, item_codes_facturados_en_periodo(socio.name, "08/2026"))

	def test_cancelacion_total_marca_facturado(self) -> None:
		socio = self._socio_activo(dni="78001003", email="prepago.total@example.com")
		cargo = self._crear_recurrente(socio.name)
		result = prepagar_cargo_socio(cargo, periodos=None, reference_date=self._HOY)
		self.assertGreaterEqual(len(result["sales_invoices"]), 6)  # jul–dic
		doc = frappe.get_doc("Cargo Socio", cargo)
		self.assertEqual(doc.estado, "Facturado")

	def test_job_mensual_no_duplica_prepagado(self) -> None:
		socio = self._socio_activo(dni="78001004", email="prepago.nodup@example.com")
		cargo = self._crear_recurrente(socio.name)
		prepagar_cargo_socio(cargo, periodos=["08/2026"], reference_date=self._HOY)
		# Dejar cargo Pendiente forzando (solo prepagamos un mes)
		frappe.db.set_value("Cargo Socio", cargo, "estado", "Pendiente")
		generar_deuda_mensual_socio(socio.name, reference_date="2026-08-01")
		self.assertEqual(
			len([c for c in item_codes_facturados_en_periodo(socio.name, "08/2026") if c == self._ITEM]),
			1,
		)

	def test_rechaza_mes_antes_de_vigencia(self) -> None:
		socio = self._socio_activo(dni="78001005", email="prepago.antes@example.com")
		cargo = self._crear_recurrente(socio.name)
		with self.assertRaises(ValidationError):
			prepagar_cargo_socio(cargo, periodos=["02/2026"], reference_date=self._HOY)

	def test_idempotencia_periodo_ya_facturado(self) -> None:
		socio = self._socio_activo(dni="78001006", email="prepago.idem@example.com")
		cargo = self._crear_recurrente(socio.name)
		first = prepagar_cargo_socio(cargo, periodos=["08/2026"], reference_date=self._HOY)
		second = prepagar_cargo_socio(cargo, periodos=["08/2026"], reference_date=self._HOY)
		self.assertEqual(len(first["sales_invoices"]), 1)
		self.assertEqual(second["sales_invoices"], [])
		self.assertIn("08/2026", second["omitidos"])
