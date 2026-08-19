"""Tests integración suscripciones — solo cuota social."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.socio_operaciones_secretaria import dar_alta_socio, dar_baja_socio
from club_management.members.services.suscripciones_socio import (
	enroll_socio_cuota_social,
	suscripciones_habilitadas,
)
from club_management.members.test_helpers import (
	MembersTestCase,
	insert_socio,
	insert_solicitud_asociacion,
	make_secretaria_user,
)
from club_management.members.workflow.solicitud_asociacion_workflow import (
	ACTION_VALIDAR,
	STATE_VALIDADA,
	ensure_solicitud_asociacion_workflow,
)
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_ITEM_CODE
from club_management.setup.suscripciones_cobro_mensual import erpnext_subscriptions_disponible


class TestSuscripcionesSocioIntegracion(MembersTestCase):
	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		ensure_solicitud_asociacion_workflow()

	def setUp(self) -> None:
		super().setUp()
		if not suscripciones_habilitadas():
			self.skipTest("ERPNext Subscriptions no instalado")
		sync_cuotas_sociales_club(update_montos_from_vigentes=True)

	def _customer_for_socio(self, socio_name: str) -> str | None:
		for field in ("socio", "custom_socio"):
			if frappe.get_meta("Customer").has_field(field):
				return frappe.db.get_value("Customer", {field: socio_name}, "name")
		return None

	def _subscription_for_customer_plan(self, customer: str, plan_name: str) -> str | None:
		subs = frappe.get_all(
			"Subscription",
			filters={
				"party_type": "Customer",
				"party": customer,
				"status": ["in", ["Active", "Trialing", "Grace Period"]],
			},
			pluck="name",
		)
		for sub in subs:
			if frappe.db.exists(
				"Subscription Plan Detail",
				{"parent": sub, "parenttype": "Subscription", "plan": plan_name},
			):
				return sub
		return None

	def _subscription_status(self, subscription_name: str) -> str:
		return frappe.db.get_value("Subscription", subscription_name, "status") or ""

	def test_validar_solicitud_crea_suscripcion_cuota_social(self) -> None:
		secretaria = make_secretaria_user("sec.sub.int@example.com")
		frappe.set_user(secretaria)
		sol = insert_solicitud_asociacion(dni="30991234", email="sub.int@example.com")
		doc = frappe.get_doc("Solicitud Asociacion", sol.name)
		with patch(
			"club_management.members.services.validar_solicitud.enqueue_validacion_pago_email"
		):
			apply_workflow(doc, ACTION_VALIDAR)
		doc.reload()
		frappe.set_user("Administrator")

		self.assertEqual(doc.workflow_state, STATE_VALIDADA)
		customer = self._customer_for_socio(doc.socio_generado)
		self.assertTrue(customer)
		plan_name = frappe.db.get_value(
			"Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}, "name"
		)
		self.assertTrue(plan_name)
		self.assertTrue(self._subscription_for_customer_plan(customer, plan_name))

	def test_enroll_cuota_social_usa_item_club_settings(self) -> None:
		socio = insert_socio(dni="30991300", email="cuota.dir@example.com", categoria="Activo")
		result = enroll_socio_cuota_social(socio.name)
		self.assertIsNotNone(result)
		assert result is not None
		self.assertTrue(result["created"])
		row = next(
			r
			for r in (frappe.get_single("Club Settings").cuotas_categoria or [])
			if r.categoria == "Activo"
		)
		self.assertEqual(row.item, CUOTA_SOCIAL_ITEM_CODE)

	def test_dar_baja_socio_cancela_suscripcion_cuota(self) -> None:
		socio = insert_socio(
			dni="30991600",
			email="baja.soc@example.com",
			categoria="Activo",
			estado="Activo",
		)
		enroll_socio_cuota_social(socio.name)
		customer = self._customer_for_socio(socio.name)
		assert customer
		plan_name = frappe.db.get_value(
			"Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}, "name"
		)
		assert plan_name
		sub_name = self._subscription_for_customer_plan(customer, plan_name)
		assert sub_name

		secretaria = make_secretaria_user("sec.baja.soc@example.com")
		frappe.set_user(secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(self._subscription_status(sub_name), "Cancelled")

	def test_dar_alta_socio_restaura_suscripcion_cuota(self) -> None:
		socio = insert_socio(
			dni="30991610",
			email="alta.soc@example.com",
			categoria="Activo",
			estado="Activo",
		)
		enroll_socio_cuota_social(socio.name)
		customer = self._customer_for_socio(socio.name)
		assert customer
		plan_name = frappe.db.get_value(
			"Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}, "name"
		)
		assert plan_name

		secretaria = make_secretaria_user("sec.alta.soc@example.com")
		frappe.set_user(secretaria)
		try:
			dar_baja_socio(socio.name, motivo="Renuncia")
			dar_alta_socio(socio.name, motivo="Quiere volver")
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(frappe.db.get_value("Socio", socio.name, "estado"), "Activo")
		self.assertTrue(self._subscription_for_customer_plan(customer, plan_name))

	def test_erpnext_subscriptions_flag(self) -> None:
		self.assertTrue(erpnext_subscriptions_disponible())
