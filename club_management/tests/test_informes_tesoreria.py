"""Tests de informes Tesorería: Ganancias y Pérdidas y Flujo de Efectivo.

Spec: `informes_tesoreria_pnl_cashflow.md`.
"""

from __future__ import annotations

import frappe

from club_management.finance.services import tesoreria_panel
from club_management.finance.services.informes_contables import (
	REPORTE_FLUJO_EFECTIVO,
	REPORTE_FLUJO_OPERATIVO,
	REPORTE_GANANCIAS_PERDIDAS,
	ejecutar_flujo_de_efectivo,
	ejecutar_ganancias_y_perdidas,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_secretaria_exists,
	make_secretaria_user,
)
from club_management.tests.test_rol_tesoreria import make_tesoreria_user

REPORTES = (REPORTE_GANANCIAS_PERDIDAS, REPORTE_FLUJO_EFECTIVO)


class TestInformesTesoreriaMeta(MembersTestCase):
	def test_reportes_existen_con_rol_tesoreria(self) -> None:
		for nombre in REPORTES:
			self.assertTrue(frappe.db.exists("Report", nombre), nombre)
			roles = {r.role for r in frappe.get_doc("Report", nombre).roles}
			self.assertIn("Tesoreria", roles, nombre)
			self.assertNotIn("Secretaria", roles, nombre)

	def test_filtros_default_mes_en_curso_y_cost_center(self) -> None:
		from club_management.finance.services.informes_contables import default_informe_filters
		from club_management.setup.icdpe_company import resolve_icdpe_company

		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")

		filtros = default_informe_filters({"cost_center": "Deportes"})
		self.assertEqual(filtros.filter_based_on, "Date Range")
		self.assertEqual(filtros.periodicity, "Monthly")
		self.assertEqual(filtros.cost_center, "Deportes")
		self.assertTrue(filtros.company)
		self.assertTrue(filtros.period_start_date)
		self.assertTrue(filtros.period_end_date)


class TestInformesTesoreriaPermisos(MembersTestCase):
	def test_force_index_es_noop_en_postgres(self) -> None:
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		gl = frappe.qb.DocType("GL Entry")
		sql = str(frappe.qb.from_(gl).select(gl.name).force_index("posting_date_company_index"))
		self.assertNotIn("FORCE INDEX", sql.upper())

	def test_tesoreria_ejecuta_pnl_y_cashflow(self) -> None:
		if not frappe.db.exists("DocType", "Account"):
			self.skipTest("ERPNext no instalado")
		user = make_tesoreria_user("tesoreria.pnl@example.com")
		frappe.set_user(user)
		try:
			try:
				cols_pnl, data_pnl, *_rest = ejecutar_ganancias_y_perdidas()
				cols_cf, data_cf, *_rest2 = ejecutar_flujo_de_efectivo()
			except frappe.PermissionError:
				raise
			except frappe.ValidationError as exc:
				self.skipTest(str(exc))
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(cols_pnl)
		self.assertIsInstance(data_pnl, list)
		self.assertTrue(cols_cf)
		self.assertIsInstance(data_cf, list)

	def test_secretaria_no_ejecuta_informes_contables(self) -> None:
		ensure_role_secretaria_exists()
		user = make_secretaria_user("secretaria.sin.pnl@example.com")
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role != "Tesoreria"]
		doc.save(ignore_permissions=True)
		frappe.set_user(user)
		try:
			with self.assertRaises(frappe.PermissionError):
				ejecutar_ganancias_y_perdidas()
			with self.assertRaises(frappe.PermissionError):
				ejecutar_flujo_de_efectivo()
		finally:
			frappe.set_user("Administrator")


class TestInformesEnPanel(MembersTestCase):
	def test_panel_tesoreria_expone_informes(self) -> None:
		user = make_tesoreria_user("tesoreria.inf.panel@example.com")
		frappe.set_user(user)
		try:
			data = tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")
		inf = data.get("informes_contables")
		self.assertIsInstance(inf, dict)
		self.assertTrue(inf["visible"])
		self.assertEqual(inf["ganancias_perdidas"], REPORTE_GANANCIAS_PERDIDAS)
		self.assertEqual(inf["flujo_efectivo"], REPORTE_FLUJO_EFECTIVO)
		self.assertEqual(inf["flujo_operativo"], REPORTE_FLUJO_OPERATIVO)

	def test_panel_secretaria_oculta_informes_contables(self) -> None:
		ensure_role_secretaria_exists()
		user = make_secretaria_user("secretaria.inf.panel@example.com")
		doc = frappe.get_doc("User", user)
		doc.roles = [r for r in doc.roles if r.role != "Tesoreria"]
		doc.save(ignore_permissions=True)
		frappe.set_user(user)
		try:
			data = tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")
		inf = data.get("informes_contables")
		self.assertIsInstance(inf, dict)
		self.assertFalse(inf["visible"])
