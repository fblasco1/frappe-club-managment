"""Tests moroso automático (spec moroso_automatico.md)."""

from __future__ import annotations

import frappe

from club_management.members.services.cargo_socio import facturar_cargo_socio
from club_management.members.services.cobranza_manual import (
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
)
from club_management.members.services.cobranza_periodica import (
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.moroso_automatico import (
	evaluar_morosos_automatico,
	evaluar_socio_moroso,
	saldo_periodo_corriente,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestMorosoAutomatico(MembersTestCase):
	_GEN = "2026-06-01"
	_SEGUNDO = "2026-06-30"
	_ITEM_EXTRA = "TEST-CARGO-MOROSO-EXTRA"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		self._secretaria = make_secretaria_user("secretaria.moroso@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)
		if not frappe.db.exists("Item", self._ITEM_EXTRA):
			item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": self._ITEM_EXTRA,
					"item_name": self._ITEM_EXTRA,
					"item_group": item_group,
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 20_000,
				}
			).insert(ignore_permissions=True)

	def _socio(self, estado: str = "Activo", **kwargs):
		socio = insert_socio(**kwargs)
		if estado != "Pendiente de Pago":
			cambiar_estado(socio.name, estado, motivo="Test moroso automático")
		return socio

	def _factura_mensual(self, socio_name: str) -> str:
		name = generar_deuda_mensual_socio(socio_name, reference_date=self._GEN)
		self.assertTrue(name)
		return name

	def test_activo_impago_pasa_moroso(self) -> None:
		socio = self._socio(dni="76001001", email="moroso.auto@example.com")
		self._factura_mensual(socio.name)
		periodo = format_periodo_cobro(self._GEN)
		self.assertGreater(saldo_periodo_corriente(socio.name, periodo), 0)

		self.assertTrue(evaluar_socio_moroso(socio.name, reference_date=self._SEGUNDO))
		socio.reload()
		self.assertEqual(socio.estado, "Moroso")
		self.assertIn(periodo, socio.motivo_ultimo_cambio_estado or "")

	def test_pagado_permance_activo(self) -> None:
		socio = self._socio(dni="76001002", email="moroso.pagado@example.com")
		invoice_name = self._factura_mensual(socio.name)
		registrar_cobro_manual(socio.name, invoice_name)

		self.assertFalse(evaluar_socio_moroso(socio.name, reference_date=self._SEGUNDO))
		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Activo")

	def test_ya_moroso_no_duplica(self) -> None:
		socio = self._socio(estado="Moroso", dni="76001003", email="moroso.ya@example.com")
		motivo_antes = frappe.db.get_value("Socio", socio.name, "motivo_ultimo_cambio_estado")

		self.assertFalse(evaluar_socio_moroso(socio.name, reference_date=self._SEGUNDO))
		self.assertEqual(
			frappe.db.get_value("Socio", socio.name, "motivo_ultimo_cambio_estado"),
			motivo_antes,
		)

	def test_suspendido_no_cambia(self) -> None:
		socio = self._socio(estado="Suspendido", dni="76001004", email="moroso.susp@example.com")
		self._factura_mensual(socio.name)

		self.assertFalse(evaluar_socio_moroso(socio.name, reference_date=self._SEGUNDO))
		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Suspendido")

	def test_cargo_extra_impago_no_moroso_si_cuota_pagada(self) -> None:
		socio = self._socio(dni="76001005", email="moroso.extra@example.com")
		invoice_mensual = self._factura_mensual(socio.name)
		registrar_cobro_manual(socio.name, invoice_mensual)

		cargo_name = frappe.get_doc(
			{
				"doctype": "Cargo Socio",
				"socio": socio.name,
				"titulo": "Viaje test moroso",
				"tipo_cargo": "Viaje",
				"modo_cobro": "Unico",
				"item": self._ITEM_EXTRA,
				"monto": 20_000,
				"fecha_desde": self._GEN,
				"estado": "Pendiente",
			}
		).insert(ignore_permissions=True).name

		frappe.set_user(self._secretaria)
		try:
			facturar_cargo_socio(cargo_name)
		finally:
			frappe.set_user("Administrator")

		periodo = format_periodo_cobro(self._GEN)
		self.assertEqual(saldo_periodo_corriente(socio.name, periodo), 0.0)
		self.assertFalse(evaluar_socio_moroso(socio.name, reference_date=self._SEGUNDO))
		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Activo")

	def test_evaluar_morosos_batch(self) -> None:
		socio = self._socio(dni="76001006", email="moroso.batch@example.com")
		self._factura_mensual(socio.name)

		result = evaluar_morosos_automatico(reference_date=self._SEGUNDO)
		self.assertIn(socio.name, result["socios"])
		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Moroso")
