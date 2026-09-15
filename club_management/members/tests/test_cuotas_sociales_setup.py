"""Tests sync cuotas sociales + ítem de suscripción."""

from __future__ import annotations

import frappe

from club_management.members.data.cuotas_sociales_vigentes import (
	CUOTA_SOCIAL_ITEM_CODE,
	CUOTAS_SOCIALES_VIGENTES,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.suscripciones_cobro_mensual import erpnext_subscriptions_disponible


class TestCuotasSocialesSetup(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_subscriptions_disponible():
			self.skipTest("ERPNext Subscriptions no instalado")

	def test_sync_cuotas_apunta_a_item_unico(self) -> None:
		sync_cuotas_sociales_club(update_montos_from_vigentes=True)
		settings = frappe.get_single("Club Settings")
		self.assertEqual(settings.item_cuota_social, CUOTA_SOCIAL_ITEM_CODE)
		by_cat = {row.categoria: row for row in (settings.cuotas_categoria or [])}
		for categoria, monto in CUOTAS_SOCIALES_VIGENTES:
			self.assertEqual(by_cat[categoria].monto, monto)
			self.assertEqual(by_cat[categoria].item, CUOTA_SOCIAL_ITEM_CODE)
		self.assertTrue(frappe.db.exists("Subscription Plan", {"item": CUOTA_SOCIAL_ITEM_CODE}))
