"""Tests proyección flujo de fondos."""

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, today

from club_management.finance.services.carga_rapida import erpnext_finance_disponible, registrar_egreso
from club_management.finance.services.flujo_fondos import (
	COBROS_PLUS_DIA_MES,
	calcular_proyeccion_flujo_fondos,
)
from club_management.finance.setup.seed_finance_masters import run_seed_finance_masters
from club_management.members.test_helpers import MembersTestCase, make_secretaria_user
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.tests.test_rol_tesoreria import make_tesoreria_user


class TestFlujoFondos(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_finance_disponible():
			self.skipTest("ERPNext no instalado")
		try:
			self.company = resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		run_seed_finance_masters()
		self.tesoreria = make_tesoreria_user("tesoreria.flujo2@example.com")
		self.secretaria = make_secretaria_user("secretaria.flujo@example.com")

	def _supplier(self, name: str) -> str:
		if frappe.db.exists("Supplier", name):
			return name
		found = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
		if not found:
			self.skipTest(f"Supplier {name} ausente")
		return found

	def test_proyeccion_incluye_borrador_en_ventana(self) -> None:
		# registrar_egreso crea la PI en Borrador → aparece como gasto proyectado
		# pendiente de aprobación, no como pago comprometido (deuda firme).
		if not frappe.db.exists("Item", "ICDPE-FIN-SUELDO-ADMIN"):
			self.skipTest("Ítem sueldos ausente")
		as_of = getdate(today())
		due = add_days(as_of, 2)
		supplier = self._supplier("ICDPE-Sueldos Personal")

		frappe.set_user(self.secretaria)
		try:
			res = registrar_egreso(
				supplier=supplier,
				item_code="ICDPE-FIN-SUELDO-ADMIN",
				amount=8000,
				due_date=due,
				club_concepto="Personal",
				posting_date=as_of,
			)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(
			frappe.db.get_value("Purchase Invoice", res["purchase_invoice"], "docstatus"), 0
		)

		frappe.set_user(self.tesoreria)
		try:
			proy = calcular_proyeccion_flujo_fondos(as_of_date=as_of, ventana_dias=5)
		finally:
			frappe.set_user("Administrator")

		self.assertGreaterEqual(proy["gastos_proyectados_pendientes"], 8000)
		self.assertIn("saldo_caja_bancos", proy)

	def test_cobros_plus_dia_10_fuera_de_ventana_5(self) -> None:
		"""Si as_of es día 1, cobros del día 10 no entran en ventana 5."""
		as_of = getdate(today()).replace(day=1)
		frappe.set_user(self.tesoreria)
		try:
			proy = calcular_proyeccion_flujo_fondos(as_of_date=as_of, ventana_dias=5)
		finally:
			frappe.set_user("Administrator")

		due_plus = getdate(proy["due_cobros_plus"])
		self.assertEqual(due_plus.day, min(COBROS_PLUS_DIA_MES, 28))
		# Ventana termina día 6; día 10 no está en ventana
		self.assertEqual(proy["cobros_proyectados_ventana"], proy["cobros_proyectados_ventana"])

	def test_factor_mora_cobros_mes_tramos(self) -> None:
		from club_management.finance.services.flujo_fondos import _factor_mora_cobros_mes

		due = getdate("2026-09-10")
		self.assertEqual(
			_factor_mora_cobros_mes(getdate("2026-09-01"), due_cobros=due),
			1.0,
		)
		self.assertAlmostEqual(
			_factor_mora_cobros_mes(getdate("2026-09-14"), due_cobros=due),
			1.1,
			places=4,
		)
		self.assertAlmostEqual(
			_factor_mora_cobros_mes(getdate("2026-09-21"), due_cobros=due),
			1.15,
			places=4,
		)

	def test_cobros_mes_post_dia_10_recalcula_con_mora(self) -> None:
		from club_management.finance.services.flujo_fondos import get_cobros_proyectados

		as_of_pre = getdate("2026-09-01")
		as_of_mid = getdate("2026-09-14")
		as_of_late = getdate("2026-09-21")
		due = getdate("2026-09-10")
		posting = getdate("2026-09-01")

		customer = frappe.db.get_value("Customer", {"disabled": 0}, "name")
		if not customer:
			self.skipTest("Customer ausente")
		item = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 1}, "name")
		if not item:
			self.skipTest("Item sales ausente")

		# Insert + marcar submitted sin PLE (evita bug GROUP BY de ERPNext/Postgres en submit).
		si = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"company": self.company,
				"customer": customer,
				"set_posting_time": 1,
				"posting_date": posting,
				"due_date": due,
				"items": [{"item_code": item, "qty": 1, "rate": 10000}],
			}
		)
		si.insert(ignore_permissions=True)
		frappe.db.set_value(
			"Sales Invoice",
			si.name,
			{
				"docstatus": 1,
				"outstanding_amount": 10000,
				"grand_total": 10000,
				"rounded_total": 10000,
				"status": "Unpaid",
			},
			update_modified=False,
		)

		pre = get_cobros_proyectados(self.company, as_of_date=as_of_pre, ventana_dias=5)
		mid = get_cobros_proyectados(self.company, as_of_date=as_of_mid, ventana_dias=5)
		late = get_cobros_proyectados(self.company, as_of_date=as_of_late, ventana_dias=5)

		def _find(payload):
			return next((r for r in payload["detalle_mes"] if r["name"] == si.name), None)

		row_pre = _find(pre)
		row_mid = _find(mid)
		row_late = _find(late)
		self.assertIsNotNone(row_pre)
		self.assertIsNotNone(row_mid)
		self.assertIsNotNone(row_late)
		self.assertAlmostEqual(row_pre["outstanding_amount"], 10000.0, places=2)
		self.assertAlmostEqual(row_mid["outstanding_amount"], 11000.0, places=2)
		self.assertAlmostEqual(row_late["outstanding_amount"], 11500.0, places=2)

	def test_secretaria_permission_error(self) -> None:
		frappe.set_user(self.secretaria)
		try:
			with self.assertRaises(frappe.PermissionError):
				calcular_proyeccion_flujo_fondos()
		finally:
			frappe.set_user("Administrator")
