"""Tests: informe pagos del día.

Spec: `club_management/specs/informe_pagos_del_dia.md`
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	registrar_cobro_compuesto,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.informe_pagos_del_dia import (
	get_informe_pagos_del_dia,
	get_pagos_del_dia_report_data,
	get_pagos_del_dia_report_summary,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
from club_management.members.test_helpers import MembersTestCase, insert_socio, make_secretaria_user


class TestInformePagosDelDia(MembersTestCase):
	_DIA = "2020-03-15"

	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		self._secretaria = make_secretaria_user("secretaria.informe.dia@example.com")
		sync_cuotas_sociales_club()
		settings = frappe.get_single("Club Settings")
		if not settings.company:
			company = frappe.db.get_value("Company", {}, "name")
			if company:
				settings.company = company
				settings.save(ignore_permissions=True)

	def _ensure_item(self, code: str, rate: float) -> str:
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": code,
					"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name")
					or "Products",
					"stock_uom": "Nos",
					"is_sales_item": 1,
					"is_stock_item": 0,
					"standard_rate": rate,
				}
			).insert(ignore_permissions=True)
		return code

	def _crear_si(self, socio_name: str, item_code: str, rate: float, *, description: str) -> str:
		from club_management.members.services.cobranza_manual import (
			_default_company,
			ensure_customer_for_socio,
		)

		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		customer = ensure_customer_for_socio(socio_name)
		doc = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": customer,
				"company": _default_company(),
				"posting_date": self._DIA,
				"due_date": self._DIA,
				"set_posting_time": 1,
				campo: socio_name,
				"items": [
					{
						"item_code": item_code,
						"qty": 1,
						"rate": rate,
						"description": description,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def test_informe_en_listado_gestion_socios(self) -> None:
		self.assertIn("Recaudacion por concepto", CLUB_DESK_REPORTS)
		self.assertNotIn("Pagos del dia", CLUB_DESK_REPORTS)

	def test_informe_del_dia_totales_medio_y_concepto(self) -> None:
		socio = insert_socio(dni="99330001", email="informe.dia@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test informe día")
		item_c = self._ensure_item("TEST-DIA-CUOTA", 4000)
		item_a = self._ensure_item("TEST-DIA-ARANCEL", 6000)
		si_c = self._crear_si(socio.name, item_c, 4000, description="Cuota social")
		si_a = self._crear_si(socio.name, item_a, 6000, description="Arancel actividad")
		sync_saldo_deuda_socio(socio.name)

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_compuesto(
				socio.name,
				[si_c, si_a],
				[
					{"mode_of_payment": "Cash", "amount": 7000},
					{"mode_of_payment": "Wire Transfer", "amount": 3000},
				],
				posting_date=self._DIA,
			)
			informe = get_informe_pagos_del_dia(self._DIA)
			summary = get_pagos_del_dia_report_summary({"fecha": self._DIA})
			data = get_pagos_del_dia_report_data({"fecha": self._DIA})
		finally:
			frappe.set_user("Administrator")

		self.assertGreaterEqual(len(informe["pagos"]), 2)
		self.assertAlmostEqual(flt(informe["total"]), 10000.0)
		por_medio = {row["mode_of_payment"]: flt(row["total"]) for row in informe["por_medio"]}
		self.assertAlmostEqual(por_medio.get("Cash", 0), 7000.0)
		self.assertAlmostEqual(por_medio.get("Wire Transfer", 0), 3000.0)
		por_concepto = {row["concepto"]: flt(row["total"]) for row in informe["por_concepto"]}
		self.assertAlmostEqual(por_concepto.get("Cuota Social", 0), 4000.0)
		self.assertAlmostEqual(por_concepto.get("Arancel actividad", 0), 6000.0)
		self.assertAlmostEqual(
			sum(flt(row["total"]) for row in informe["por_concepto"]),
			flt(informe["total"]),
		)

		# Header: total + medios (sin conceptos)
		summary_labels = [row["label"] for row in summary]
		self.assertEqual(summary_labels[0], "Total recaudado")
		self.assertTrue(any(label in ("Efectivo", "Cash") for label in summary_labels))
		self.assertTrue(any(label in ("Transferencia", "Wire Transfer") for label in summary_labels))
		self.assertTrue(all(not str(label).startswith("Concepto:") for label in summary_labels))
		self.assertTrue(any("Total Cuota Social" in str(row.get("concepto") or "") for row in data))
		self.assertTrue(any("Total Arancel actividad" in str(row.get("concepto") or "") for row in data))

	def test_listado_ordenado_por_apellido_nombre(self) -> None:
		socio_z = insert_socio(
			dni="99330002",
			email="informe.z@example.com",
			apellido="Zárate",
			nombre="Ana",
		)
		socio_a = insert_socio(
			dni="99330003",
			email="informe.a@example.com",
			apellido="Álvarez",
			nombre="Bruno",
		)
		cambiar_estado(socio_z.name, "Activo", motivo="Test orden z")
		cambiar_estado(socio_a.name, "Activo", motivo="Test orden a")
		item = self._ensure_item("TEST-DIA-ORDEN", 1000)
		si_z = self._crear_si(socio_z.name, item, 1000, description="Cuota social")
		si_a = self._crear_si(socio_a.name, item, 1000, description="Cuota social")

		frappe.set_user(self._secretaria)
		try:
			registrar_cobro_compuesto(
				socio_z.name,
				[si_z],
				[{"mode_of_payment": "Cash", "amount": 1000}],
				posting_date=self._DIA,
			)
			registrar_cobro_compuesto(
				socio_a.name,
				[si_a],
				[{"mode_of_payment": "Cash", "amount": 1000}],
				posting_date=self._DIA,
			)
			informe = get_informe_pagos_del_dia(self._DIA)
		finally:
			frappe.set_user("Administrator")

		labels = [row["socio_label"] for row in informe["lineas"]]
		self.assertGreaterEqual(len(labels), 2)
		# Álvarez antes que Zárate (orden sin acentos)
		idx_a = next(i for i, label in enumerate(labels) if "Álvarez" in label or "Alvarez" in label)
		idx_z = next(i for i, label in enumerate(labels) if "Zárate" in label or "Zarate" in label)
		self.assertLess(idx_a, idx_z)


if __name__ == "__main__":
	import unittest

	unittest.main()
