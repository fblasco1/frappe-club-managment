"""Tests de callback y conciliación Supervielle 4.2."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import frappe

from club_management.finance.services.payment_log import (
	PROVIDER_SUPERVIELLE,
	record_gateway_transaction,
)
from club_management.integrations.supervielle.reconciliation import (
	build_callback_hash,
	process_callback,
	validate_callback_payload,
)
from club_management.integrations.supervielle_api import SupervielleIntegrationError
from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.spaces.helpers import make_socio_portal_user

SECRET = "callback-secret"


def _callback(*, status: str = "3", portal_id: str = "PORTAL-100") -> dict[str, str]:
	payload = {
		"IdPago": "SIC-CALLBACK-100",
		"IdPagoPortal": portal_id,
		"FechaHoraPago": "2026-09-08 10:30:00",
		"CodMedioPago": "TC",
		"MedioPago": "Tarjeta",
		"Importe": "100.00",
		"CodigoEstado": status,
		"Estado": "Pagado" if status == "3" else "Validado",
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


class TestCallbackContract(unittest.TestCase):
	def test_hash_contractual_y_comparacion(self) -> None:
		payload = _callback()
		validated = validate_callback_payload(payload, SECRET)
		self.assertEqual(validated["IdPago"], "SIC-CALLBACK-100")

	def test_hash_incorrecto_y_campos_extra_fallan(self) -> None:
		bad = {**_callback(), "Hash": "bad"}
		with self.assertRaises(SupervielleIntegrationError):
			validate_callback_payload(bad, SECRET)
		extra = {**_callback(), "unexpected": "x"}
		with self.assertRaises(SupervielleIntegrationError):
			validate_callback_payload(extra, SECRET)


class TestCallbackPersistence(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		if not frappe.db.exists("DocType", "Payment Gateway Event"):
			self.skipTest("Payment Gateway Event no migrado")
		record_gateway_transaction(
			merchant_transaction_id="SIC-CALLBACK-100",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			ignore_permissions=True,
		)

	def test_estado_3_replay_no_duplica_evento_ni_crea_pe(self) -> None:
		first = process_callback(_callback(), secret_key=SECRET)
		second = process_callback(_callback(), secret_key=SECRET)
		self.assertEqual(first["event"], second["event"])
		self.assertEqual(first["result"], "audited")
		self.assertEqual(
			frappe.db.count(
				"Payment Gateway Event",
				{"gateway_transaction_id": "PORTAL-100", "status_code": "3"},
			),
			1,
		)
		log = frappe.get_doc(
			"Payment Log",
			{"merchant_transaction_id": "SIC-CALLBACK-100"},
		)
		self.assertEqual(log.gateway_transaction_id, "PORTAL-100")
		self.assertFalse(log.payment_entry)

	def test_id_bancario_no_se_reutiliza(self) -> None:
		record_gateway_transaction(
			merchant_transaction_id="SIC-CALLBACK-OTHER",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			ignore_permissions=True,
		)
		other = _callback(portal_id="PORTAL-100")
		other["IdPago"] = "SIC-CALLBACK-OTHER"
		other["Hash"] = build_callback_hash(other, SECRET)
		process_callback(_callback(), secret_key=SECRET)
		with self.assertRaises(frappe.ValidationError):
			process_callback(other, secret_key=SECRET)

	def test_socio_no_puede_leer_eventos(self) -> None:
		user = make_socio_portal_user("socio.gateway.event@example.com")
		self.assertFalse(
			frappe.has_permission("Payment Gateway Event", ptype="read", user=user)
		)

	def test_reverso_solo_queda_para_revision(self) -> None:
		payload = _callback(status="7")
		payload["Estado"] = "Reversado"
		payload["Hash"] = build_callback_hash(payload, SECRET)
		result = process_callback(payload, secret_key=SECRET)
		self.assertEqual(result["result"], "manual_review")
		self.assertFalse(result["payment_entry"])


class TestCallbackCreatesPaymentEntry(MembersTestCase):
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
			dni="99013062",
			email="callback.pe@example.com",
			numero_socio=99013062,
		)
		cambiar_estado(socio.name, "Activo", motivo="Test callback PE")
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
			merchant_transaction_id="SIC-CALLBACK-100",
			provider=PROVIDER_SUPERVIELLE,
			status="Recibido",
			amount=100,
			currency="ARS",
			sales_invoice=self.invoice.name,
			socio=socio.name,
			ignore_permissions=True,
		)

	def test_estado_5_crea_un_solo_payment_entry(self) -> None:
		paid = process_callback(_callback(status="3"), secret_key=SECRET)
		self.assertEqual(paid["result"], "audited")
		self.assertFalse(paid["payment_entry"])
		payload = _callback(status="5")
		first = process_callback(payload, secret_key=SECRET)
		second = process_callback(payload, secret_key=SECRET)
		self.assertEqual(first["result"], "conciled")
		self.assertEqual(first["payment_entry"], second["payment_entry"])
		self.assertEqual(
			frappe.db.get_value("Payment Entry", first["payment_entry"], "docstatus"),
			1,
		)
		log = frappe.get_doc(
			"Payment Log",
			{"merchant_transaction_id": "SIC-CALLBACK-100"},
		)
		self.assertEqual(log.status, "Conciliado")
		self.assertEqual(log.payment_entry, first["payment_entry"])

	def test_importe_parcial_no_crea_payment_entry(self) -> None:
		payload = _callback(status="5")
		payload["Importe"] = "90.00"
		payload["Hash"] = build_callback_hash(payload, SECRET)
		with self.assertRaises(frappe.ValidationError):
			process_callback(payload, secret_key=SECRET)
		self.assertFalse(
			frappe.db.get_value(
				"Payment Log",
				{"merchant_transaction_id": "SIC-CALLBACK-100"},
				"payment_entry",
			)
		)

	def test_fallo_submit_no_marca_conciliado(self) -> None:
		payload = _callback(status="5")
		with (
			patch(
				"club_management.integrations.supervielle.reconciliation._create_payment_entry",
				side_effect=RuntimeError("submit failed"),
			),
			self.assertRaises(RuntimeError),
		):
			process_callback(payload, secret_key=SECRET)
		log = frappe.get_doc(
			"Payment Log",
			{"merchant_transaction_id": "SIC-CALLBACK-100"},
		)
		self.assertEqual(log.status, "Recibido")
		self.assertFalse(log.payment_entry)
