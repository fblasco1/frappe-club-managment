"""Tests corrección CTO COMP Básquet impagas (spec corregir_cto_comp_basquet_periodo.md)."""

from __future__ import annotations

import uuid

import frappe
from frappe.utils import flt, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.scripts.fix_tarifas_cto_comp_basquet_impagas import (
	TARIFA_ESC_FEM,
	TARIFA_RESTO_BASQ,
	run,
	tarifa_cto_comp_basquet,
)
from club_management.scripts.informe_concepto_cobranza import ITEM_CUOTA_COMPLEMENTARIA

PERIODO = "11/2026"


def _dni() -> str:
	return f"79{uuid.uuid4().hex[:6]}"


class TestTarifaCtoCompBasquetHelper(MembersTestCase):
	def test_clasifica_esc_fem_y_resto(self) -> None:
		self.assertEqual(tarifa_cto_comp_basquet("CTO COMP BASQ ESC/FEM"), TARIFA_ESC_FEM)
		self.assertEqual(
			tarifa_cto_comp_basquet("CTO COMP BASQ/FEM (11/2026)"),
			TARIFA_ESC_FEM,
		)
		self.assertEqual(
			tarifa_cto_comp_basquet("CTO COMP BASQUET ESC"),
			TARIFA_ESC_FEM,
		)
		self.assertEqual(
			tarifa_cto_comp_basquet("CTO COMP BASQ TIRA A/B/FLEX (11/2026)"),
			TARIFA_RESTO_BASQ,
		)
		self.assertEqual(
			tarifa_cto_comp_basquet("CTO COMP BASQUET TIRA A/B/FLEX"),
			TARIFA_RESTO_BASQ,
		)
		self.assertIsNone(tarifa_cto_comp_basquet("CTO COMP VOLEY ESC"))
		self.assertIsNone(tarifa_cto_comp_basquet("Adicional Basquet Escuelita"))


class TestFixTarifasCtoCompBasquetImpagas(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		if not frappe.db.exists("Item", ITEM_CUOTA_COMPLEMENTARIA):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": ITEM_CUOTA_COMPLEMENTARIA,
					"item_name": "Cargo varios",
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "All Item Groups",
					"is_stock_item": 0,
					"is_sales_item": 1,
					"standard_rate": 1,
				}
			).insert(ignore_permissions=True)

	def _factura(
		self,
		dni: str,
		*,
		description: str,
		rate: float,
		outstanding: float | None = None,
	) -> tuple[str, str]:
		socio = insert_socio(dni=dni, email=f"cto.fix.{dni}@example.com")
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()
		inv = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": today(),
				"due_date": today(),
				_campo_socio_en(SALES_INVOICE_DOCTYPE): socio.name,
				_campo_periodo_cobro(): PERIODO,
				"remarks": f"CTO COMP {PERIODO}",
				"items": [
					{
						"item_code": ITEM_CUOTA_COMPLEMENTARIA,
						"qty": 1,
						"rate": rate,
						"description": description,
					}
				],
			}
		)
		inv.insert(ignore_permissions=True)
		inv.submit()
		if outstanding is not None:
			frappe.db.set_value(
				SALES_INVOICE_DOCTYPE,
				inv.name,
				"outstanding_amount",
				outstanding,
				update_modified=False,
			)
		return inv.name, socio.name

	def _cargo(self, socio_name: str, titulo: str, monto: float) -> str:
		return (
			frappe.get_doc(
				{
					"doctype": "Cargo Socio",
					"socio": socio_name,
					"titulo": titulo,
					"tipo_cargo": "Otro",
					"modo_cobro": "Recurrente",
					"item": ITEM_CUOTA_COMPLEMENTARIA,
					"monto": monto,
					"fecha_desde": "2026-11-01",
					"fecha_hasta": "2026-12-31",
					"estado": "Pendiente",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)

	def test_dry_run_esc_fem_sin_modificar(self) -> None:
		name, _socio = self._factura(
			_dni(),
			description="CTO COMP BASQ ESC/FEM (11/2026)",
			rate=4000,
		)
		report = run(periodo_cobro=PERIODO, dry_run=True)
		muestra = next((r for r in report["muestra_facturas"] if r["invoice"] == name), None)
		self.assertIsNotNone(muestra)
		self.assertEqual(muestra["action"], "would_patch")
		self.assertEqual(muestra["lineas"][0]["new_rate"], TARIFA_ESC_FEM)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice Item", {"parent": name}, "rate")), 4000)

	def test_dry_run_tira_a_7000(self) -> None:
		name, _socio = self._factura(
			_dni(),
			description="CTO COMP BASQ TIRA A/B/FLEX (11/2026)",
			rate=6000,
		)
		report = run(periodo_cobro=PERIODO, dry_run=True)
		muestra = next((r for r in report["muestra_facturas"] if r["invoice"] == name), None)
		self.assertIsNotNone(muestra)
		self.assertEqual(muestra["lineas"][0]["new_rate"], TARIFA_RESTO_BASQ)

	def test_apply_protegido(self) -> None:
		name, _socio = self._factura(
			_dni(),
			description="CTO COMP BASQ ESC/FEM",
			rate=4000,
		)
		with self.assertRaises(frappe.ValidationError):
			run(periodo_cobro=PERIODO, dry_run=False, confirm="")
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice Item", {"parent": name}, "rate")), 4000)

	def test_apply_parchea_e_idempotente(self) -> None:
		name, socio = self._factura(
			_dni(),
			description="CTO COMP BASQ ESC/FEM (11/2026)",
			rate=4000,
		)
		old_out = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount"))
		report = run(periodo_cobro=PERIODO, dry_run=False, confirm="local-dev")
		muestra = next((r for r in report["muestra_facturas"] if r["invoice"] == name), None)
		self.assertIsNotNone(muestra)
		self.assertEqual(muestra["action"], "patched")
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice Item", {"parent": name}, "rate")),
			TARIFA_ESC_FEM,
		)
		new_out = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "outstanding_amount"))
		self.assertEqual(new_out, old_out + 2000)

		again = run(periodo_cobro=PERIODO, dry_run=False, confirm="local-dev")
		self.assertFalse(any(r["invoice"] == name for r in again["muestra_facturas"]))
		self.assertTrue(socio)

	def test_pagada_no_se_toca(self) -> None:
		name, _socio = self._factura(
			_dni(),
			description="CTO COMP BASQ TIRA A/B/FLEX",
			rate=6000,
			outstanding=0,
		)
		report = run(periodo_cobro=PERIODO, dry_run=False, confirm="local-dev")
		self.assertFalse(any(r["invoice"] == name for r in report["muestra_facturas"]))
		self.assertEqual(
			flt(frappe.db.get_value("Sales Invoice Item", {"parent": name}, "rate")),
			6000,
		)

	def test_cargo_pendiente_se_actualiza(self) -> None:
		socio = insert_socio(dni=_dni(), email=f"cto.cargo.{uuid.uuid4().hex[:8]}@example.com")
		cargo = self._cargo(socio.name, "CTO COMP BASQUET TIRA A/B/FLEX", 6000)
		run(periodo_cobro=PERIODO, dry_run=False, confirm="local-dev")
		self.assertEqual(flt(frappe.db.get_value("Cargo Socio", cargo, "monto")), TARIFA_RESTO_BASQ)

	def test_voley_ignorado(self) -> None:
		name, _socio = self._factura(
			_dni(),
			description="CTO COMP VOLEY ESC (11/2026)",
			rate=4000,
		)
		report = run(periodo_cobro=PERIODO, dry_run=True)
		self.assertFalse(any(r["invoice"] == name for r in report["muestra_facturas"]))
