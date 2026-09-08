"""Tests Frappe: Supervielle Settings, publicación y Payment Log."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import frappe
from frappe.exceptions import PermissionError, ValidationError

from club_management.finance.permissions import ensure_role_tesoreria_exists
from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.integrations.supervielle.payload import SANDBOX_API_URL, SANDBOX_CONCEPTO, SANDBOX_CUIT
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.members.services.cobranza_manual import (
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
	insert_socio,
	make_secretaria_user,
)


SANDBOX_SECRET = "14D6C372-F28C-4DED-BE02-71E3A6C94415"


def _make_role_user(email: str, role: str) -> str:
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if role not in {r.role for r in user.roles}:
			user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": role,
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	).insert(ignore_permissions=True)
	return email


class _FakeResponse:
	def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
		self.status_code = status_code
		self._payload = payload
		self.text = frappe.as_json(payload)

	def json(self) -> dict[str, Any]:
		return self._payload


class TestSupervielleSettingsAndPublicacion(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_tesoreria_exists()
		ensure_role_socio_exists()
		if not frappe.db.exists("DocType", "Supervielle Settings"):
			self.skipTest("Supervielle Settings no migrado")
		self._save_settings()

	def _save_settings(self) -> None:
		try:
			settings = frappe.get_single("Supervielle Settings")
		except frappe.DoesNotExistError:
			settings = frappe.new_doc("Supervielle Settings")
		settings.sandbox_mode = 1
		settings.cuit_emisor = SANDBOX_CUIT
		settings.api_url = SANDBOX_API_URL
		settings.concepto_default = SANDBOX_CONCEPTO
		settings.secret_key = SANDBOX_SECRET
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("Supervielle Settings", "Supervielle Settings")

	def test_settings_sandbox_defaults(self) -> None:
		settings = frappe.get_single("Supervielle Settings")
		self.assertTrue(int(settings.sandbox_mode or 0))
		self.assertEqual((settings.cuit_emisor or "").replace("-", ""), SANDBOX_CUIT)
		self.assertEqual(settings.api_url, SANDBOX_API_URL)
		self.assertEqual(settings.concepto_default, SANDBOX_CONCEPTO)

	def test_socio_no_puede_publicar(self) -> None:
		from club_management.integrations.supervielle.client import publicar_boton_pago_factura

		socio_user = _make_role_user("socio.botonpago@example.com", "Socio")
		frappe.set_user(socio_user)
		try:
			with self.assertRaises(PermissionError):
				publicar_boton_pago_factura("ACC-SINV-NOEXISTE")
		finally:
			frappe.set_user("Administrator")


class TestSuperviellePublicacionInvoice(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if frappe.db.db_type != "postgres":
			self.skipTest("Solo PostgreSQL")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext Sales Invoice no instalado")
		if not frappe.db.exists("DocType", "Supervielle Settings"):
			self.skipTest("Supervielle Settings no migrado")
		apply_patch()
		self._item_code = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
		if not self._item_code:
			self.skipTest("Sin ítem de venta")
		ensure_role_tesoreria_exists()
		try:
			settings = frappe.get_single("Supervielle Settings")
		except frappe.DoesNotExistError:
			settings = frappe.new_doc("Supervielle Settings")
		settings.sandbox_mode = 1
		settings.cuit_emisor = SANDBOX_CUIT
		settings.api_url = SANDBOX_API_URL
		settings.concepto_default = SANDBOX_CONCEPTO
		settings.secret_key = SANDBOX_SECRET
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("Supervielle Settings", "Supervielle Settings")
		self._secretaria = make_secretaria_user("secretaria.botonpago@example.com")

	def _crear_factura(self, *, rate: float = 19500) -> tuple[Any, Any]:
		socio = insert_socio(dni="99012062", email="botonpago.si@example.com", numero_socio=99012062)
		cambiar_estado(socio.name, "Activo", motivo="Test boton pago")
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		campo_socio = _campo_socio_en("Sales Invoice")
		inv = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": _default_company(),
				"posting_date": frappe.utils.today(),
				"due_date": "2026-09-10",
				campo_socio: socio.name,
				"items": [{"item_code": self._item_code, "qty": 1, "rate": rate}],
			}
		)
		inv.insert(ignore_permissions=True)
		inv.submit()
		return socio, inv

	def test_publicar_crea_payment_log_y_devuelve_url(self) -> None:
		from club_management.integrations.supervielle.client import publicar_boton_pago

		socio, inv = self._crear_factura()
		session = MagicMock()
		session.post.return_value = _FakeResponse(
			200,
			{"UrlBotonPago": "https://pago.example/xyz", "IdTransaccion": "SV-TX-001"},
		)
		result = publicar_boton_pago(inv.name, session=session)
		self.assertEqual(result.url, "https://pago.example/xyz")
		self.assertEqual(result.transaction_id, "SV-TX-001")
		self.assertTrue(frappe.db.exists("Payment Log", {"gateway_transaction_id": "SV-TX-001"}))
		log = frappe.get_doc("Payment Log", {"gateway_transaction_id": "SV-TX-001"})
		self.assertEqual(log.provider, "Banco Supervielle")
		self.assertEqual(log.status, "Recibido")
		self.assertEqual(log.sales_invoice, inv.name)
		self.assertEqual(log.socio, socio.name)
		self.assertNotIn(SANDBOX_SECRET, frappe.as_json(log.payload_json or {}))
		session.post.assert_called_once()
		posted_url = session.post.call_args.args[0]
		self.assertEqual(posted_url, SANDBOX_API_URL)

	def test_error_http_registra_log_rechazado(self) -> None:
		from club_management.integrations.supervielle.client import publicar_boton_pago

		_socio, inv = self._crear_factura(rate=100)
		session = MagicMock()
		session.post.return_value = _FakeResponse(500, {"error": "boom"})
		with self.assertRaises(SupervielleIntegrationError):
			publicar_boton_pago(inv.name, session=session)
		rechazados = frappe.get_all(
			"Payment Log",
			filters={"sales_invoice": inv.name, "status": "Rechazado"},
			pluck="name",
		)
		self.assertTrue(rechazados)

	def test_factura_pagada_no_publica(self) -> None:
		from club_management.integrations.supervielle.client import publicar_boton_pago

		_socio, inv = self._crear_factura(rate=100)
		frappe.db.set_value("Sales Invoice", inv.name, "outstanding_amount", 0)
		session = MagicMock()
		with self.assertRaises(ValidationError):
			publicar_boton_pago(inv.name, session=session)
		session.post.assert_not_called()
