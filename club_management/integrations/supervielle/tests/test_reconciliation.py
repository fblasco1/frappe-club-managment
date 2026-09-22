"""Tests de callback: strict/audit, PE estado 5 e idempotencia.

Spec: `club_management/specs/supervielle_conciliacion_rendiciones.md`
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	record_gateway_transaction,
)
from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.integrations.supervielle.reconciliation import (
	build_callback_hash,
	process_callback,
	validate_callback_payload,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.members.services.cobranza_manual import (
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio

SECRET = "callback-secret-strict"


def _callback(*, status: str = "5", portal_id: str = "PORTAL-STRICT-1", pago: str = "SIC-STRICT-1") -> dict[str, str]:
	payload = {
		"IdPago": pago,
		"IdPagoPortal": portal_id,
		"FechaHoraPago": "2026-09-08 10:30:00",
		"CodMedioPago": "TC",
		"MedioPago": "Tarjeta",
		"Importe": "100.00",
		"CodigoEstado": status,
		"Estado": "Validado" if status == "5" else ("Pagado" if status == "3" else "Rechazado"),
		"FechaHoraCambioEstado": "2026-09-08 10:31:00",
		"CodigoRechazo": "",
		"Rechazo": "",
		"Cuotas": "1",
		"CodigoAutorizacion": "AUTH-1",
		"Ticket": "T-1",
		"Mail": "socio@example.com",
		"Observaciones": "",
	}
	payload["Hash"] = build_callback_hash(payload, SECRET)
	return payload


class TestCallbackStrictMode(unittest.TestCase):
	def test_hash_invalido_strict_lanza(self) -> None:
		bad = {**_callback(), "Hash": "deadbeef"}
		with self.assertRaises(SupervielleIntegrationError):
			validate_callback_payload(bad, SECRET, strict=True)

	def test_hash_invalido_no_strict_pasa_esquema(self) -> None:
		bad = {**_callback(), "Hash": "deadbeef"}
		validated = validate_callback_payload(bad, SECRET, strict=False)
		self.assertEqual(validated["IdPago"], "SIC-STRICT-1")


class TestCallbackAuditAndIdempotency(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Payment Gateway Event"):
			self.skipTest("Payment Gateway Event no migrado")
		record_gateway_transaction(
			merchant_transaction_id="SIC-STRICT-1",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			ignore_permissions=True,
		)

	def test_strict_false_registra_hash_warning_y_sigue(self) -> None:
		bad = {**_callback(status="3"), "Hash": "bad-hash"}
		result = process_callback(bad, secret_key=SECRET, strict=False)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["result"], "audited")
		self.assertTrue(
			frappe.db.exists(
				"Payment Gateway Event",
				{"merchant_transaction_id": "SIC-STRICT-1", "processing_result": "hash_warning"},
			)
		)

	def test_rechazado_no_crea_payment_entry(self) -> None:
		payload = _callback(status="9")
		payload["Estado"] = "Rechazado"
		payload["Hash"] = build_callback_hash(payload, SECRET)
		result = process_callback(payload, secret_key=SECRET, strict=True)
		self.assertEqual(result["result"], "manual_review")
		self.assertFalse(result["payment_entry"])


class TestCallbackApprovedIdempotent(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not erpnext_cobranza_disponible():
			self.skipTest("ERPNext no disponible")
		apply_patch()
		item_code = frappe.db.get_value("Item", {"is_sales_item": 1}, "name")
		if not item_code:
			self.skipTest("Sin ítem de venta")
		socio = insert_socio(
			dni="99014001",
			email="callback.idem@example.com",
			numero_socio=99014001,
		)
		cambiar_estado(socio.name, "Activo", motivo="Test callback idem")
		customer = ensure_customer_for_socio(socio.name, skip_permission_check=True)
		campo_socio = _campo_socio_en("Sales Invoice")
		self.invoice = frappe.get_doc(
			{
				"doctype": "Sales Invoice",
				"customer": customer,
				"company": _default_company(),
				"posting_date": frappe.utils.today(),
				"due_date": frappe.utils.today(),
				campo_socio: socio.name,
				"items": [{"item_code": item_code, "qty": 1, "rate": 100}],
			}
		)
		self.invoice.insert(ignore_permissions=True)
		self.invoice.submit()
		record_gateway_transaction(
			merchant_transaction_id="SIC-STRICT-1",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			sales_invoice=self.invoice.name,
			socio=socio.name,
			ignore_permissions=True,
		)

	def test_estado_5_crea_pe_y_reintento_idempotente(self) -> None:
		payload = _callback(status="5")
		first = process_callback(payload, secret_key=SECRET, strict=True)
		second = process_callback(payload, secret_key=SECRET, strict=True)
		self.assertEqual(first["result"], "conciled")
		self.assertTrue(second["replayed"])
		self.assertEqual(first["payment_entry"], second["payment_entry"])
		self.assertEqual(
			frappe.db.count("Payment Entry", {"reference_no": "PORTAL-STRICT-1", "docstatus": 1}),
			1,
		)

	def test_pe_existente_por_reference_no_omite_duplicado(self) -> None:
		payload = _callback(status="5")
		first = process_callback(payload, secret_key=SECRET, strict=True)
		# Simula reintento sin evento (borra event_key uniqueness path via otro status time)
		# pero con PE ya presente: process_callback debe devolver replayed.
		with patch(
			"club_management.integrations.supervielle.reconciliation._create_payment_entry"
		) as create_pe:
			again = process_callback(payload, secret_key=SECRET, strict=True)
			create_pe.assert_not_called()
		self.assertTrue(again["replayed"])
		self.assertEqual(again["payment_entry"], first["payment_entry"])
