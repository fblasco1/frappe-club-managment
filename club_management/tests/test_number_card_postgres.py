"""Tests workaround Number Card + PostgreSQL."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from club_management.integrations.number_card_postgres import get_result


class TestNumberCardPostgres(FrappeTestCase):
	def test_get_result_aggregate_uses_no_order_by(self) -> None:
		doc = {
			"name": "Total Stock Value",
			"function": "Sum",
			"aggregate_function_based_on": "stock_value",
			"document_type": "Bin",
		}
		with patch.object(frappe, "get_list", return_value=[{"result": 42}]) as mocked:
			value = get_result(doc, [])
		self.assertEqual(value, 42)
		_, kwargs = mocked.call_args
		self.assertIsNone(kwargs.get("order_by"))
