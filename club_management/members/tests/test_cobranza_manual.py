"""Tests cobranza manual (MVP sin pagos online)."""

from __future__ import annotations

import frappe

from club_management.members.api.cobranza_desk import list_facturas_pendientes
from club_management.members.services.cobranza_manual import (
	erpnext_cobranza_disponible,
	list_facturas_pendientes_socio,
	resolve_cuota_social,
	sync_saldo_deuda_socio,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestCobranzaManual(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = "secretaria_cobro@example.com"
		if not frappe.db.exists("User", self._secretaria):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			).insert(ignore_permissions=True)

	def test_resolve_cuota_vitalicio_es_cero(self) -> None:
		socio = insert_socio()
		frappe.db.set_value("Socio", socio.name, "categoria", "Vitalicio")
		monto, item = resolve_cuota_social(socio.name)
		self.assertEqual(monto, 0.0)
		self.assertIsNone(item)

	def test_resolve_cuota_desde_club_settings(self) -> None:
		if not frappe.db.exists("DocType", "Club Settings"):
			self.skipTest("Club Settings no migrado")
		settings = frappe.get_single("Club Settings")
		settings.cuotas_categoria = []
		settings.append(
			"cuotas_categoria",
			{"categoria": "Activo", "monto": 15000, "item": None},
		)
		settings.save(ignore_permissions=True)

		socio = insert_socio(categoria="Activo")
		monto, _item = resolve_cuota_social(socio.name)
		self.assertEqual(monto, 15000.0)

	def test_list_facturas_pendientes_vacio_sin_facturas(self) -> None:
		socio = insert_socio()
		self.assertEqual(list_facturas_pendientes_socio(socio.name), [])
		frappe.set_user(self._secretaria)
		try:
			self.assertEqual(list_facturas_pendientes(socio.name), [])
		finally:
			frappe.set_user("Administrator")

	def test_sync_saldo_sin_erpnext_devuelve_cero(self) -> None:
		socio = insert_socio()
		if erpnext_cobranza_disponible():
			saldo = sync_saldo_deuda_socio(socio.name)
			self.assertGreaterEqual(saldo, 0.0)
		else:
			self.assertEqual(sync_saldo_deuda_socio(socio.name), 0.0)
