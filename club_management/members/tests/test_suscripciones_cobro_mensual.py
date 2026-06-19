"""Tests bootstrap suscripciones y enroll de socios."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.setup.suscripciones_cobro_mensual import (
	CLUB_FEE_ITEMS,
	ITEM_GROUP_NAME,
	PRICE_LIST_NAME,
	enroll_member_to_subscription,
	erpnext_subscriptions_disponible,
	setup_club_fee_items_and_plans,
)


class TestSuscripcionesCobroMensual(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not erpnext_subscriptions_disponible():
			self.skipTest("ERPNext Subscriptions no instalado")

	def _ensure_customer(self, name: str = "TEST-SUB-CUSTOMER") -> str:
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

	def test_setup_crea_item_group_items_planes_y_precios(self) -> None:
		result = setup_club_fee_items_and_plans()

		self.assertTrue(frappe.db.exists("Item Group", ITEM_GROUP_NAME))
		for spec in CLUB_FEE_ITEMS:
			self.assertTrue(frappe.db.exists("Item", spec.item_code))
			self.assertEqual(frappe.db.get_value("Item", spec.item_code, "is_stock_item"), 0)
			self.assertEqual(frappe.db.get_value("Item", spec.item_code, "item_name"), spec.item_name)
			self.assertTrue(
				frappe.db.exists(
					"Item Price",
					{"item_code": spec.item_code, "price_list": PRICE_LIST_NAME},
				)
			)
			self.assertTrue(frappe.db.exists("Subscription Plan", spec.plan_name))
			plan = frappe.get_doc("Subscription Plan", spec.plan_name)
			self.assertEqual(plan.billing_interval, "Month")
			self.assertEqual(plan.billing_interval_count, 1)
			self.assertEqual(plan.item, spec.item_code)

		self.assertIn("items", result)
		self.assertEqual(len(result["subscription_plans"]), len(CLUB_FEE_ITEMS))

	def test_setup_es_idempotente(self) -> None:
		setup_club_fee_items_and_plans()
		count_items = frappe.db.count("Item", {"item_code": ["in", [s.item_code for s in CLUB_FEE_ITEMS]]})
		setup_club_fee_items_and_plans()
		self.assertEqual(
			frappe.db.count("Item", {"item_code": ["in", [s.item_code for s in CLUB_FEE_ITEMS]]}),
			count_items,
		)

	def test_enroll_crea_subscription_activa(self) -> None:
		setup_club_fee_items_and_plans()
		customer = self._ensure_customer()
		plan = CLUB_FEE_ITEMS[0].plan_name

		result = enroll_member_to_subscription(customer, plan)
		self.assertTrue(result["created"])
		self.assertTrue(frappe.db.exists("Subscription", result["subscription"]))

		sub = frappe.get_doc("Subscription", result["subscription"])
		self.assertEqual(sub.party_type, "Customer")
		self.assertEqual(sub.party, customer)
		self.assertEqual(sub.status, "Active")
		self.assertEqual(int(sub.submit_invoice or 0), 1)
		self.assertEqual(len(sub.plans), 1)
		self.assertEqual(sub.plans[0].plan, plan)

	def test_enroll_no_duplica_mismo_plan(self) -> None:
		setup_club_fee_items_and_plans()
		customer = self._ensure_customer("TEST-SUB-CUSTOMER-DUP")
		plan = CLUB_FEE_ITEMS[0].plan_name

		first = enroll_member_to_subscription(customer, plan)
		second = enroll_member_to_subscription(customer, plan)

		self.assertTrue(first["created"])
		self.assertFalse(second["created"])
		self.assertEqual(first["subscription"], second["subscription"])

	def test_enroll_rechaza_cliente_invalido(self) -> None:
		setup_club_fee_items_and_plans()
		with self.assertRaises(frappe.ValidationError):
			enroll_member_to_subscription("CLIENTE-INEXISTENTE-XYZ", CLUB_FEE_ITEMS[0].plan_name)
