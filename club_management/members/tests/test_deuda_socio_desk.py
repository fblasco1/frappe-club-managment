"""Tests detalle de deuda en Socio (spec deuda_socio_desk.md)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.members.api.cobranza_desk import list_detalle_deuda
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	generar_cargo_socio,
	get_detalle_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestDeudaSocioDesk(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._secretaria = make_secretaria_user("secretaria.deuda@example.com")
		self._item = self._ensure_item("TEST-DEUDA-EXTRA", 8_500)
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.incluir_cargos_extra_en_deuda_mensual = 1
		settings.incluir_aranceles_en_deuda_mensual = 0
		settings.save(ignore_permissions=True)

	def _ensure_item(self, code: str, rate: float) -> str:
		if frappe.db.exists("Item", code):
			frappe.db.set_value("Item", code, "standard_rate", rate)
			return code
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": item_group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"standard_rate": rate,
			}
		).insert(ignore_permissions=True)
		return code

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test deuda socio desk")
		return socio

	def _crear_cargo_recurrente(self, socio_name: str) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": socio_name,
					"titulo": "Cuota Federativa Junio",
					"tipo_cargo": "Cuota Federativa",
					"modo_cobro": "Recurrente",
					"item": self._item,
					"monto": 8_500,
					"fecha_desde": "2026-06-01",
					"fecha_hasta": "2026-12-31",
					"estado": "Pendiente",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_generar_cargo_incluye_cargo_extra_recurrente(self) -> None:
		socio = self._socio_activo(dni="75001001", email="deuda.gen@example.com")
		self._crear_cargo_recurrente(socio.name)

		frappe.set_user(self._secretaria)
		try:
			invoice_names = generar_cargo_socio(socio.name, incluir_actividades=False)
		finally:
			frappe.set_user("Administrator")

		item_codes: set[str] = set()
		for invoice_name in invoice_names:
			invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
			item_codes |= {row.item_code for row in invoice.items}
		self.assertIn(self._item, item_codes)

	def test_detalle_deuda_incluye_periodo_cobro(self) -> None:
		socio = self._socio_activo(dni="75001004", email="deuda.periodo@example.com")
		frappe.set_user(self._secretaria)
		try:
			invoices = generar_cargo_socio(
				socio.name,
				incluir_actividades=False,
				reference_date="2026-03-01",
			)
			detalle = get_detalle_deuda_socio(socio.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(invoices)
		self.assertTrue(detalle["facturas"])
		periodos = {row.get("periodo_cobro") for row in detalle["facturas"]}
		self.assertIn("03/2026", periodos)

	def test_detalle_deuda_ordenado_por_periodo_cronologico(self) -> None:
		socio = self._socio_activo(dni="75001005", email="deuda.orden@example.com")
		frappe.set_user(self._secretaria)
		try:
			generar_cargo_socio(socio.name, incluir_actividades=False, reference_date="2026-01-01")
			generar_cargo_socio(socio.name, incluir_actividades=False, reference_date="2025-12-01")
			detalle = get_detalle_deuda_socio(socio.name)
		finally:
			frappe.set_user("Administrator")

		periodos = [row.get("periodo_cobro") for row in detalle["facturas"] if row.get("periodo_cobro")]
		self.assertIn("12/2025", periodos)
		self.assertIn("01/2026", periodos)
		idx_dic = periodos.index("12/2025")
		idx_ene = periodos.index("01/2026")
		self.assertLess(idx_dic, idx_ene)

	def test_detalle_deuda_muestra_factura_y_cargo_pendiente(self) -> None:
		socio = self._socio_activo(dni="75001002", email="deuda.det@example.com")
		# El cargo único se factura automáticamente al crearse.
		frappe.get_doc(
			{
				"doctype": "Cargo Socio",
				"socio": socio.name,
				"titulo": "Multa test",
				"tipo_cargo": "Multa",
				"modo_cobro": "Unico",
				"item": self._item,
				"monto": 5_000,
				"fecha_desde": "2026-06-01",
				"estado": "Pendiente",
			}
		).insert(ignore_permissions=True)

		frappe.set_user(self._secretaria)
		try:
			detalle = get_detalle_deuda_socio(socio.name)
			api_detalle = list_detalle_deuda(socio.name)
		finally:
			frappe.set_user("Administrator")

		self.assertGreater(flt(detalle["saldo_deuda"]), 0)
		self.assertEqual(len(detalle["facturas"]), 1)
		self.assertTrue(detalle["facturas"][0]["lineas"])
		self.assertEqual(detalle["facturas"][0]["lineas"][0]["concepto"], "Multa test")
		self.assertEqual(detalle["cargos_pendientes"], [])
		self.assertEqual(api_detalle["saldo_deuda"], detalle["saldo_deuda"])

	def test_sync_saldo_no_actualiza_modified(self) -> None:
		socio = self._socio_activo(dni="75001003", email="deuda.mod@example.com")
		frappe.get_doc(
			{
				"doctype": "Cargo Socio",
				"socio": socio.name,
				"titulo": "Multa modified",
				"tipo_cargo": "Multa",
				"modo_cobro": "Unico",
				"item": self._item,
				"monto": 3_000,
				"fecha_desde": "2026-06-01",
				"estado": "Pendiente",
			}
		).insert(ignore_permissions=True)

		modified_antes = frappe.db.get_value("Socio", socio.name, "modified")
		frappe.db.set_value("Socio", socio.name, "nombre", "Nombre Test", update_modified=False)

		frappe.set_user(self._secretaria)
		try:
			get_detalle_deuda_socio(socio.name)
		finally:
			frappe.set_user("Administrator")

		modified_despues = frappe.db.get_value("Socio", socio.name, "modified")
		self.assertEqual(str(modified_antes), str(modified_despues))
