"""Tests del panel operativo de Tesorería (GF-6)."""

from __future__ import annotations

import frappe

from club_management.finance.permissions import ensure_finance_panel_access
from club_management.finance.services import tesoreria_panel
from club_management.finance.setup.purchase_order_permissions import (
	remove_purchase_order_club_permissions,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_secretaria_exists,
	make_secretaria_user,
)
from club_management.tests.test_rol_tesoreria import make_tesoreria_user


class TestTesoreriaPanelAcceso(MembersTestCase):
	def test_secretaria_accede_al_panel(self) -> None:
		ensure_role_secretaria_exists()
		user = make_secretaria_user("secretaria.panel@example.com")
		frappe.set_user(user)
		try:
			data = tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")
		self.assertIn("borradores_pendientes", data)
		self.assertIn("facturas_pagas", data)
		self.assertIn("cobros_recibidos", data)
		self.assertIsInstance(data["borradores_pendientes"], list)

	def test_tesoreria_accede_al_panel(self) -> None:
		user = make_tesoreria_user("tesoreria.panel@example.com")
		frappe.set_user(user)
		try:
			data = tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")
		self.assertIn("facturas_pagas", data)
		self.assertTrue(data["informes_contables"]["visible"])
		self.assertEqual(data["informes_contables"]["ganancias_perdidas"], "Ganancias y Perdidas")

	def test_panel_incluye_liquidez_a_5_dias(self) -> None:
		"""Día 1: el Tesorero ve liquidez y borradores sin abrir el Script Report."""
		user = make_tesoreria_user("tesoreria.liq@example.com")
		frappe.set_user(user)
		try:
			data = tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")

		liq = data.get("liquidez")
		self.assertIsInstance(liq, dict)
		self.assertEqual(liq["ventana_dias"], 5)
		self.assertIn("liquidez_proyectada", liq)
		self.assertIn("gastos_proyectados_pendientes", liq)
		self.assertTrue(liq.get("liquidez_proyectada_label"))
		self.assertTrue(liq.get("gastos_proyectados_pendientes_label"))

	def test_usuario_sin_rol_no_accede(self) -> None:
		email = "sinrol.panel@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "SinRol",
					"send_welcome_email": 0,
					"roles": [],
				}
			).insert(ignore_permissions=True)
		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				ensure_finance_panel_access()
			with self.assertRaises(frappe.PermissionError):
				tesoreria_panel.get_panel_data()
		finally:
			frappe.set_user("Administrator")


class TestTesoreriaPanelEstructura(MembersTestCase):
	def test_filas_tienen_cuenta_y_centro_costo(self) -> None:
		# Cada fila del panel debe exponer cuenta y centro de costo (aunque vacíos).
		for lista in (
			tesoreria_panel.facturas_compra_borrador(),
			tesoreria_panel.facturas_compra_pagas_ultimo_mes(),
			tesoreria_panel.cobros_recibidos_ultimo_mes(),
		):
			for fila in lista:
				self.assertIn("cuenta", fila)
				self.assertIn("centro_costo", fila)
				self.assertIn("importe_label", fila)
				self.assertIn("fecha_label", fila)


class TestPurchaseOrderSinAccesoClub(MembersTestCase):
	def test_roles_club_pierden_acceso_a_purchase_order(self) -> None:
		if not frappe.db.exists("DocType", "Purchase Order"):
			self.skipTest("ERPNext no instalado")
		remove_purchase_order_club_permissions()
		for role in ("Secretaria", "Tesoreria", "System Manager"):
			self.assertFalse(
				frappe.db.exists(
					"Custom DocPerm",
					{"parent": "Purchase Order", "role": role, "permlevel": 0},
				),
				f"No debe quedar Custom DocPerm de Purchase Order para {role}",
			)
