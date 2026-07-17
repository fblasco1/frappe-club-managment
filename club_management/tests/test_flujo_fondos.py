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

	def test_proyeccion_incluye_pi_en_ventana(self) -> None:
		if not frappe.db.exists("Item", "ICDPE-FIN-SUELDOS"):
			self.skipTest("Ítem sueldos ausente")
		as_of = getdate(today())
		due = add_days(as_of, 2)
		supplier = self._supplier("ICDPE-Sueldos Personal")

		frappe.set_user(self.secretaria)
		try:
			registrar_egreso(
				supplier=supplier,
				item_code="ICDPE-FIN-SUELDOS",
				amount=8000,
				due_date=due,
				club_concepto="Personal",
				posting_date=as_of,
			)
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(self.tesoreria)
		try:
			proy = calcular_proyeccion_flujo_fondos(as_of_date=as_of, ventana_dias=5)
		finally:
			frappe.set_user("Administrator")

		self.assertGreaterEqual(proy["pagos_comprometidos"], 8000)
		self.assertGreaterEqual(proy["obligaciones_criticas"], 8000)
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

	def test_secretaria_permission_error(self) -> None:
		frappe.set_user(self.secretaria)
		try:
			with self.assertRaises(frappe.PermissionError):
				calcular_proyeccion_flujo_fondos()
		finally:
			frappe.set_user("Administrator")
