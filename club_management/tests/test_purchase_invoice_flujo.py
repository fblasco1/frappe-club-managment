"""Tests del flujo de egresos Borrador (Secretaría) → Aprobación (Tesorería).

Spec: `club_management/specs/flujo_egresos_borrador_aprobacion.md`.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_days, getdate, today

from club_management.finance.services.carga_rapida import (
	erpnext_finance_disponible,
	registrar_egreso,
	resolve_buying_cost_center,
)
from club_management.finance.services.flujo_fondos import calcular_proyeccion_flujo_fondos
from club_management.finance.services.purchase_invoice_validation import validate_egreso
from club_management.finance.services import tesoreria_panel
from club_management.finance.setup.purchase_invoice_permissions import (
	ensure_purchase_invoice_permissions,
)
from club_management.finance.setup.purchase_order_permissions import (
	remove_purchase_order_club_permissions,
)
from club_management.finance.setup.seed_finance_masters import run_seed_finance_masters
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_secretaria_exists,
	make_secretaria_user,
)
from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.tests.test_rol_tesoreria import make_tesoreria_user

PI = "Purchase Invoice"
ITEM_SUELDOS = "ICDPE-FIN-SUELDO-ADMIN"


class _FinanceBase(MembersTestCase):
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
		ensure_role_secretaria_exists()
		ensure_purchase_invoice_permissions()
		remove_purchase_order_club_permissions()
		self.tesoreria = make_tesoreria_user("tesoreria.pi@example.com")
		self.secretaria = make_secretaria_user("secretaria.pi@example.com")

	def _supplier(self, name: str = "ICDPE-Sueldos Personal") -> str:
		if frappe.db.exists("Supplier", name):
			return name
		found = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
		if not found:
			self.skipTest(f"Supplier {name} ausente")
		return found

	def _crear_pi_borrador(self, *, due_date, amount: float = 5000.0) -> frappe.Document:
		if not frappe.db.exists("Item", ITEM_SUELDOS):
			self.skipTest("Ítem sueldos ausente")
		cc = resolve_buying_cost_center(ITEM_SUELDOS, self.company)
		doc = frappe.get_doc(
			{
				"doctype": PI,
				"company": self.company,
				"supplier": self._supplier(),
				"posting_date": getdate(today()),
				"due_date": getdate(due_date),
				"set_posting_time": 1,
				"update_stock": 0,
				"bill_no": f"TEST-{frappe.generate_hash(length=6)}",
				"bill_date": getdate(today()),
				"items": [{"item_code": ITEM_SUELDOS, "qty": 1, "rate": amount, "cost_center": cc}],
				"club_concepto": "Personal",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc


class TestPurchaseInvoicePermisos(_FinanceBase):
	def test_secretaria_crea_pero_no_submittea(self) -> None:
		frappe.set_user(self.secretaria)
		try:
			self.assertTrue(frappe.has_permission(PI, "create"))
			self.assertTrue(frappe.has_permission(PI, "write"))
			self.assertFalse(frappe.has_permission(PI, "submit"))
			self.assertFalse(frappe.has_permission(PI, "cancel"))
		finally:
			frappe.set_user("Administrator")

	def test_tesoreria_full(self) -> None:
		frappe.set_user(self.tesoreria)
		try:
			self.assertTrue(frappe.has_permission(PI, "create"))
			self.assertTrue(frappe.has_permission(PI, "submit"))
			self.assertTrue(frappe.has_permission(PI, "cancel"))
		finally:
			frappe.set_user("Administrator")

	def test_roles_club_sin_purchase_order(self) -> None:
		if not frappe.db.exists("DocType", "Purchase Order"):
			self.skipTest("ERPNext no instalado")
		for user in (self.secretaria, self.tesoreria):
			frappe.set_user(user)
			try:
				self.assertFalse(
					frappe.has_permission("Purchase Order", "read"),
					f"{user} no debe acceder a Purchase Order",
				)
			finally:
				frappe.set_user("Administrator")


class TestPurchaseInvoiceValidacion(_FinanceBase):
	def _pi_doc(self, *, due_date, cost_center) -> frappe.Document:
		return frappe.get_doc(
			{
				"doctype": PI,
				"company": self.company,
				"supplier": self._supplier(),
				"posting_date": getdate(today()),
				"due_date": due_date,
				"items": [
					{"item_code": ITEM_SUELDOS, "qty": 1, "rate": 1000, "cost_center": cost_center}
				],
			}
		)

	def test_falta_due_date_error(self) -> None:
		doc = self._pi_doc(due_date=None, cost_center="X")
		with self.assertRaises(frappe.ValidationError):
			validate_egreso(doc, "validate")

	def test_item_sin_cost_center_error(self) -> None:
		doc = self._pi_doc(due_date=getdate(today()), cost_center=None)
		with self.assertRaises(frappe.ValidationError):
			validate_egreso(doc, "validate")

	def test_ok_no_lanza(self) -> None:
		doc = self._pi_doc(due_date=getdate(today()), cost_center="Administración")
		validate_egreso(doc, "validate")  # no debe lanzar

	def test_hook_registrado(self) -> None:
		hooks = (
			frappe.get_hooks("doc_events").get("Purchase Invoice", {})
			if frappe.get_hooks("doc_events")
			else {}
		)
		self.assertIn(
			"club_management.finance.services.purchase_invoice_validation.validate_egreso",
			frappe.get_hooks("doc_events", {}).get("Purchase Invoice", {}).get("validate", []),
		)


class TestRegistrarEgresoDraft(_FinanceBase):
	def test_registrar_egreso_crea_borrador(self) -> None:
		if not frappe.db.exists("Item", ITEM_SUELDOS):
			self.skipTest("Ítem sueldos ausente")
		res = registrar_egreso(
			supplier=self._supplier(),
			item_code=ITEM_SUELDOS,
			amount=6000,
			due_date=add_days(getdate(today()), 3),
			club_concepto="Personal",
			skip_permission_check=True,
		)
		name = res["purchase_invoice"]
		self.assertTrue(name)
		self.assertEqual(frappe.db.get_value(PI, name, "docstatus"), 0)


class TestTesoreriaPanelBorradores(_FinanceBase):
	def test_panel_lista_borradores(self) -> None:
		self._crear_pi_borrador(due_date=add_days(getdate(today()), 4), amount=7000)
		filas = tesoreria_panel.facturas_compra_borrador()
		self.assertTrue(filas)
		for fila in filas:
			self.assertIn("cuenta", fila)
			self.assertIn("centro_costo", fila)
			self.assertEqual(fila["estado"], "Borrador")
		data = tesoreria_panel.get_panel_data()
		self.assertIn("borradores_pendientes", data)


class TestFlujoFondosBorrador(_FinanceBase):
	def test_borrador_en_gastos_proyectados(self) -> None:
		as_of = getdate(today())
		self._crear_pi_borrador(due_date=add_days(as_of, 2), amount=9000)
		frappe.set_user(self.tesoreria)
		try:
			proy = calcular_proyeccion_flujo_fondos(as_of_date=as_of, ventana_dias=5)
		finally:
			frappe.set_user("Administrator")
		self.assertGreaterEqual(proy.get("gastos_proyectados_pendientes", 0), 9000)
