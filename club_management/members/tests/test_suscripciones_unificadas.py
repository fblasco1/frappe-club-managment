"""Tests suscripciones unificadas + idempotencia mensual por concepto."""

from __future__ import annotations

import frappe

from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	generar_cargo_socio,
	item_codes_facturados_en_periodo,
)
from club_management.members.services.cobranza_periodica import (
	format_periodo_cobro,
	generar_deuda_mensual_socio,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.services.suscripciones_socio import (
	expected_plan_names_for_socio,
	sync_suscripciones_socio,
	suscripciones_habilitadas,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio
from club_management.setup.suscripciones_cobro_mensual import (
	enroll_member_to_subscription,
	erpnext_subscriptions_disponible,
)


class TestSuscripcionesUnificadas(MembersTestCase):
	_REFERENCE = "2026-07-01"

	def setUp(self) -> None:
		super().setUp()
		if not suscripciones_habilitadas():
			self.skipTest("ERPNext Subscriptions no instalado")
		sync_cuotas_sociales_club(update_montos_from_vigentes=True)

	def _socio_activo(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test suscripciones")
		return socio

	def _customer(self, socio_name: str) -> str:
		from club_management.members.services.cobranza_manual import ensure_customer_for_socio

		return ensure_customer_for_socio(socio_name, skip_permission_check=True)

	def test_enroll_dos_planes_misma_suscripcion(self) -> None:
		setup = sync_cuotas_sociales_club()
		customer = self._ensure_customer("TEST-SUB-UNIF")
		plan_cuota = setup.get("plan") or frappe.db.get_value(
			"Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}, "name"
		)
		assert plan_cuota
		enroll_member_to_subscription(customer, plan_cuota)
		# Segundo plan ficticio: reutilizar el mismo si no hay otro ítem en test
		second = enroll_member_to_subscription(customer, plan_cuota)
		self.assertFalse(second["created"])
		subs = frappe.get_all(
			"Subscription",
			filters={"party": customer, "status": ["!=", "Cancelled"]},
		)
		self.assertEqual(len(subs), 1)
		sub = frappe.get_doc("Subscription", subs[0].name)
		self.assertEqual(int(sub.submit_invoice or 0), 0)

	def _ensure_customer(self, name: str) -> str:
		if frappe.db.exists("Customer", name):
			return name
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": name,
				"customer_type": "Individual",
				"customer_group": frappe.db.get_single_value("Selling Settings", "customer_group")
				or "Individual",
				"territory": frappe.db.get_single_value("Selling Settings", "territory") or "All Territories",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_sync_suscripciones_socio_crea_plan_cuota(self) -> None:
		socio = self._socio_activo(dni="73101001", email="sub.unif@example.com")
		result = sync_suscripciones_socio(socio.name)
		self.assertTrue(result.get("subscription"))
		plans = expected_plan_names_for_socio(socio.name)
		self.assertTrue(plans)

	def test_no_duplica_cargo_manual_mismo_mes(self) -> None:
		from club_management.members.services.cobranza_manual import erpnext_cobranza_disponible

		if not erpnext_cobranza_disponible():
			self.skipTest("Sales Invoice no disponible")
		socio = self._socio_activo(dni="73101002", email="dup.cargo@example.com")
		sync_suscripciones_socio(socio.name)
		generar_deuda_mensual_socio(socio.name, reference_date=self._REFERENCE)
		periodo = format_periodo_cobro(self._REFERENCE)
		self.assertIn(CUOTA_SOCIAL_ITEM_CODE, item_codes_facturados_en_periodo(socio.name, periodo))
		with self.assertRaises(frappe.ValidationError):
			generar_cargo_socio(socio.name, reference_date=self._REFERENCE)

	def test_submit_invoice_cero_en_nueva_suscripcion(self) -> None:
		if not erpnext_subscriptions_disponible():
			self.skipTest("Subscriptions no disponible")
		customer = self._ensure_customer("TEST-SUBMIT-0")
		plan = frappe.db.get_value("Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}, "name")
		assert plan
		result = enroll_member_to_subscription(customer, plan)
		sub = frappe.get_doc("Subscription", result["subscription"])
		self.assertEqual(int(sub.submit_invoice or 0), 0)
