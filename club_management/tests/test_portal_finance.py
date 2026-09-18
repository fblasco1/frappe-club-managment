"""Estado de cuenta del portal socio (BL-6d).

Spec: `club_management/specs/portal_socio_estado_cuenta.md`
"""

from __future__ import annotations

import contextlib
import importlib
import json
from types import ModuleType
from typing import Iterator

import frappe
from frappe.utils import add_days, flt, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.services.user_provisioning import provision_user_for_socio
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
	make_secretaria_user,
)


FINANCE_API_MODULE = "club_management.members.api.portal_finance"


@contextlib.contextmanager
def as_user(user: str) -> Iterator[None]:
	previous = frappe.session.user
	try:
		frappe.set_user(user)
		yield
	finally:
		frappe.set_user(previous)


def finance_api() -> ModuleType:
	return importlib.import_module(FINANCE_API_MODULE)


class TestPortalFinance(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		apply_patch()
		frappe.set_user("Administrator")
		ensure_role_socio_exists()
		self._secretaria = make_secretaria_user("secretaria.portal.finance@example.com")
		self._item_code = self._ensure_item("TEST-PORTAL-FINANCE", 2500)

		self.socio_a = self._socio_portal(
			dni="78440001",
			email="portal.fin.a@example.com",
			nombre="Ana",
			apellido="Deuda",
		)
		self.socio_b = self._socio_portal(
			dni="78440002",
			email="portal.fin.b@example.com",
			nombre="Bruno",
			apellido="Ajeno",
		)

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

	def _socio_portal(self, *, dni: str, email: str, nombre: str, apellido: str):
		socio = insert_socio(dni=dni, email=email, nombre=nombre, apellido=apellido)
		cambiar_estado(socio.name, "Activo", motivo="Test portal finance")
		provision_user_for_socio(socio.name)
		socio.reload()
		return socio

	def _crear_si(
		self,
		socio_name: str,
		*,
		rate: float = 2500,
		submit: bool = True,
		description: str = "Cuota portal",
		posting_offset: int = 0,
	):
		campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
		posting = add_days(today(), posting_offset)
		doc = frappe.get_doc(
			{
				"doctype": SALES_INVOICE_DOCTYPE,
				"customer": ensure_customer_for_socio(socio_name, skip_permission_check=True),
				"company": _default_company(),
				"posting_date": posting,
				"due_date": posting,
				"set_posting_time": 1,
				campo: socio_name,
				"items": [
					{
						"item_code": self._item_code,
						"qty": 1,
						"rate": rate,
						"description": description,
					}
				],
			}
		)
		doc.insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def test_guest_recibe_permission_error(self) -> None:
		with as_user("Guest"):
			with self.assertRaises(frappe.PermissionError):
				finance_api().get_estado_cuenta_socio()

	def test_socio_ve_factura_propia_y_no_la_ajena(self) -> None:
		propia = self._crear_si(self.socio_a.name, description="Cuota A")
		ajena = self._crear_si(self.socio_b.name, description="Cuota B")

		with as_user(self.socio_a.user):
			payload = finance_api().get_estado_cuenta_socio()

		nombres = [row["name"] for row in payload["facturas_pendientes"]]
		self.assertIn(propia.name, nombres)
		self.assertNotIn(ajena.name, nombres)
		fila = next(row for row in payload["facturas_pendientes"] if row["name"] == propia.name)
		self.assertEqual(fila["concepto"], "Cuota A")
		self.assertIn("posting_date", fila)
		self.assertIn("due_date", fila)
		self.assertAlmostEqual(flt(fila["outstanding_amount"]), 2500.0)

	def test_excluye_borrador_y_cancelada(self) -> None:
		exigible = self._crear_si(self.socio_a.name, description="Exigible")
		borrador = self._crear_si(self.socio_a.name, description="Borrador", submit=False)
		cancelada = self._crear_si(self.socio_a.name, description="Cancelada")
		cancelada.cancel()

		with as_user(self.socio_a.user):
			payload = finance_api().get_estado_cuenta_socio()

		nombres = [row["name"] for row in payload["facturas_pendientes"]]
		self.assertEqual(nombres, [exigible.name])
		self.assertNotIn(borrador.name, nombres)
		self.assertNotIn(cancelada.name, nombres)

	def test_pagos_recientes_con_recibo_y_json(self) -> None:
		factura = self._crear_si(self.socio_a.name, description="Cuota cobrada")
		frappe.set_user(self._secretaria)
		try:
			pe_name = registrar_cobro_manual(
				self.socio_a.name,
				factura.name,
				mode_of_payment="Cash",
			)
		finally:
			frappe.set_user("Administrator")

		with as_user(self.socio_a.user):
			payload = finance_api().get_estado_cuenta_socio()

		self.assertEqual(payload["facturas_pendientes"], [])
		self.assertEqual(len(payload["pagos_recientes"]), 1)
		pago = payload["pagos_recientes"][0]
		self.assertEqual(pago["name"], pe_name)
		self.assertEqual(pago["mode_of_payment"], "Cash")
		self.assertAlmostEqual(flt(pago["paid_amount"]), 2500.0)
		self.assertIn("recibo_url", pago)
		self.assertIn(pe_name, pago["recibo_url"])
		serialized = json.dumps(payload)
		self.assertIn(pe_name, serialized)
		self.assertEqual(json.loads(serialized)["pagos_recientes"][0]["name"], pe_name)

	def test_pagos_recientes_limita_a_cinco(self) -> None:
		from unittest.mock import patch

		fake_rows = [
			{
				"payment_entry": f"PE-FAKE-{idx}",
				"posting_date": today(),
				"mode_of_payment": "Cash",
				"paid_amount": 100 + idx,
			}
			for idx in range(8)
		]
		with as_user(self.socio_a.user):
			with patch(
				"club_management.members.api.portal_finance.list_historial_pagos_socio",
				return_value=fake_rows,
			) as mocked:
				payload = finance_api().get_estado_cuenta_socio()
		mocked.assert_called()
		self.assertEqual(mocked.call_args.kwargs.get("limit"), 5)
		self.assertEqual(len(payload["pagos_recientes"]), 5)
