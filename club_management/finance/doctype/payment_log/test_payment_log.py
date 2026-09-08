"""Tests del DocType Payment Log (spec payment_log.md)."""

from __future__ import annotations

import frappe
from frappe.exceptions import ValidationError

from club_management.finance.permissions import ROLE_TESORERIA, ensure_role_tesoreria_exists
from club_management.finance.services.payment_log import record_gateway_transaction
from club_management.members.test_helpers import (
	MembersTestCase,
	ensure_role_socio_exists,
)


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


class TestPaymentLog(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")
		ensure_role_tesoreria_exists()
		ensure_role_socio_exists()

	def test_alta_con_id_unico(self) -> None:
		doc = record_gateway_transaction(
			gateway_transaction_id="TX-UNIQUE-001",
			provider="Cobrand",
			gateway_reference="REF-001",
		)
		self.assertTrue(frappe.db.exists("Payment Log", doc.name))
		self.assertEqual(doc.status, "Recibido")
		self.assertEqual(doc.gateway_transaction_id, "TX-UNIQUE-001")

	def test_siro_no_es_proveedor_valido(self) -> None:
		with self.assertRaises(ValidationError):
			record_gateway_transaction(
				gateway_transaction_id="TX-SIRO-001",
				provider="SIRO",
				gateway_reference="REF-SIRO",
			)
		self.assertFalse(
			frappe.db.exists("Payment Log", {"gateway_transaction_id": "TX-SIRO-001"})
		)

	def test_idempotencia_mismo_id_misma_referencia(self) -> None:
		first = record_gateway_transaction(
			gateway_transaction_id="TX-IDEM-001",
			provider="Banco Supervielle",
			gateway_reference="INV-100",
		)
		second = record_gateway_transaction(
			gateway_transaction_id="TX-IDEM-001",
			provider="Banco Supervielle",
			gateway_reference="INV-100",
		)
		self.assertEqual(first.name, second.name)
		self.assertEqual(
			frappe.db.count("Payment Log", {"gateway_transaction_id": "TX-IDEM-001"}),
			1,
		)

	def test_no_reutilizar_id_en_otro_pago(self) -> None:
		original = record_gateway_transaction(
			gateway_transaction_id="TX-REUSE-001",
			provider="Cobrand",
			gateway_reference="INV-AAA",
		)
		with self.assertRaises(ValidationError):
			record_gateway_transaction(
				gateway_transaction_id="TX-REUSE-001",
				provider="Cobrand",
				gateway_reference="INV-BBB",
			)
		fresh = frappe.get_doc("Payment Log", original.name)
		self.assertEqual(fresh.gateway_reference, "INV-AAA")

	def test_campos_de_pago_inmutables(self) -> None:
		doc = record_gateway_transaction(
			gateway_transaction_id="TX-IMM-001",
			provider="Cobrand",
			gateway_reference="REF-IMM",
		)
		doc.gateway_transaction_id = "TX-IMM-HACK"
		with self.assertRaises(ValidationError):
			doc.save()
		doc.reload()
		self.assertEqual(doc.gateway_transaction_id, "TX-IMM-001")
		with self.assertRaises(ValidationError):
			doc.delete()
		self.assertTrue(frappe.db.exists("Payment Log", doc.name))

	def test_estado_puede_avanzar_sin_tocar_id(self) -> None:
		doc = record_gateway_transaction(
			gateway_transaction_id="TX-STATUS-001",
			provider="Banco Supervielle",
			gateway_reference="REF-STATUS",
		)
		doc.status = "Conciliado"
		doc.save()
		doc.reload()
		self.assertEqual(doc.status, "Conciliado")
		self.assertEqual(doc.gateway_transaction_id, "TX-STATUS-001")

	def test_socio_sin_acceso_tesoreria_solo_lectura(self) -> None:
		socio = _make_role_user("socio.paymentlog@example.com", "Socio")
		tesoreria = _make_role_user("tesoreria.paymentlog@example.com", ROLE_TESORERIA)

		frappe.set_user(socio)
		try:
			self.assertFalse(frappe.has_permission("Payment Log", ptype="read"))
			self.assertFalse(frappe.has_permission("Payment Log", ptype="create"))
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(tesoreria)
		try:
			self.assertTrue(frappe.has_permission("Payment Log", ptype="read"))
			self.assertFalse(frappe.has_permission("Payment Log", ptype="create"))
			self.assertFalse(frappe.has_permission("Payment Log", ptype="write"))
			self.assertFalse(frappe.has_permission("Payment Log", ptype="delete"))
		finally:
			frappe.set_user("Administrator")
