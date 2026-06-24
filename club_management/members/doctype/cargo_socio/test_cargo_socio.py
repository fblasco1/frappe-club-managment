"""Tests DocType Cargo Socio (spec cargo_extra_socio.md)."""

from __future__ import annotations

import frappe
from frappe.exceptions import PermissionError, ValidationError

from club_management.members.services.cargo_socio import (
	cancelar_cargo_socio,
	facturar_cargo_socio,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_periodica import generar_deuda_mensual_socio
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestCargoSocio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._secretaria = make_secretaria_user("secretaria.cargo@example.com")
		self._item = self._ensure_item("TEST-CARGO-EXTRA", 15_000)
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
		settings.incluir_cargos_extra_en_deuda_mensual = 1
		settings.incluir_aranceles_en_deuda_mensual = 1
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
		cambiar_estado(socio.name, "Activo", motivo="Test cargo extra")
		return socio

	def _crear_cargo(
		self,
		socio_name: str,
		*,
		modo_cobro: str = "Unico",
		monto: float = 15_000,
		fecha_desde: str = "2026-06-01",
		fecha_hasta: str | None = None,
	) -> str:
		payload: dict = {
			"doctype": "Cargo Socio",
			"socio": socio_name,
			"titulo": "Cuota Federativa Test",
			"tipo_cargo": "Cuota Federativa",
			"modo_cobro": modo_cobro,
			"item": self._item,
			"monto": monto,
			"fecha_desde": fecha_desde,
			"estado": "Pendiente",
		}
		if fecha_hasta:
			payload["fecha_hasta"] = fecha_hasta
		return frappe.get_doc(payload).insert(ignore_permissions=True).name

	def test_crear_cargo_unico_se_factura_automaticamente(self) -> None:
		socio = self._socio_activo(dni="74001001", email="cargo.unico@example.com")
		name = self._crear_cargo(socio.name)

		cargo = frappe.get_doc("Cargo Socio", name)
		self.assertEqual(cargo.estado, "Facturado")
		self.assertTrue(cargo.sales_invoice)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, cargo.sales_invoice)
		self.assertEqual(invoice.docstatus, 1)
		self.assertEqual(len(invoice.items), 1)
		self.assertEqual(invoice.items[0].item_code, self._item)
		self.assertGreater(sync_saldo_deuda_socio(socio.name), 0)

	def test_crear_cargo_unico_como_secretaria_se_factura(self) -> None:
		socio = self._socio_activo(dni="74001002", email="cargo.fact@example.com")

		frappe.set_user(self._secretaria)
		try:
			cargo_name = self._crear_cargo(socio.name)
		finally:
			frappe.set_user("Administrator")

		cargo = frappe.get_doc("Cargo Socio", cargo_name)
		self.assertEqual(cargo.estado, "Facturado")
		self.assertTrue(cargo.sales_invoice)

	def test_cancelar_cargo_recurrente_pendiente(self) -> None:
		socio = self._socio_activo(dni="74001003", email="cargo.cancel@example.com")
		cargo_name = self._crear_cargo(
			socio.name,
			modo_cobro="Recurrente",
			fecha_desde="2026-06-01",
			fecha_hasta="2026-12-31",
		)
		self.assertEqual(frappe.db.get_value("Cargo Socio", cargo_name, "estado"), "Pendiente")

		frappe.set_user(self._secretaria)
		try:
			cancelar_cargo_socio(cargo_name)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Cargo Socio", cargo_name, "estado"), "Cancelado")

	def test_recurrente_requiere_fecha_hasta(self) -> None:
		socio = self._socio_activo(dni="74001004", email="cargo.rec@example.com")
		with self.assertRaises(ValidationError):
			self._crear_cargo(socio.name, modo_cobro="Recurrente")

	def test_cargo_recurrente_en_deuda_mensual(self) -> None:
		socio = self._socio_activo(dni="74001005", email="cargo.mensual@example.com")
		self._crear_cargo(
			socio.name,
			modo_cobro="Recurrente",
			fecha_desde="2026-06-01",
			fecha_hasta="2026-12-31",
		)
		invoice_name = generar_deuda_mensual_socio(socio.name, reference_date="2026-06-01")
		self.assertTrue(invoice_name)
		invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
		item_codes = {row.item_code for row in invoice.items}
		self.assertIn(self._item, item_codes)

	def test_aislamiento_entre_socios(self) -> None:
		socio_a = self._socio_activo(dni="74001006", email="cargo.a@example.com")
		socio_b = self._socio_activo(dni="74001007", email="cargo.b@example.com")
		self._crear_cargo(socio_a.name, monto=12_000)

		email_b = f"socio_{socio_b.dni}@example.com"
		if not frappe.db.exists("User", email_b):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email_b,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Socio", socio_b.name, "user", email_b)

		frappe.set_user(email_b)
		try:
			rows = frappe.get_list("Cargo Socio", pluck="name")
			self.assertEqual(rows, [])
		finally:
			frappe.set_user("Administrator")

	def test_usuario_sin_rol_no_factura(self) -> None:
		socio = self._socio_activo(dni="74001008", email="cargo.perm@example.com")
		cargo_name = self._crear_cargo(socio.name)
		email = f"socio_{socio.dni}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)

		frappe.set_user(email)
		try:
			with self.assertRaises(PermissionError):
				facturar_cargo_socio(cargo_name)
		finally:
			frappe.set_user("Administrator")
