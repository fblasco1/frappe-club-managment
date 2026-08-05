"""Tests limpieza Item Groups residuales (spec cleanup_residual_item_groups.md)."""

from __future__ import annotations

import frappe

from club_management.finance.setup.cleanup_residual_item_groups import (
	RESIDUAL_CUOTAS_SOCIALES,
	RESIDUAL_FINANZAS_EGRESOS,
	run_cleanup_residual_item_groups,
)
from club_management.finance.setup.icdpe_finance_items import (
	DEFAULT_ITEM_GROUP_ROOT,
	GROUP_REMUNERACIONES,
	ensure_egresos_item_group_tree,
)
from club_management.finance.setup.icdpe_income_item_groups import (
	LEAF_CUOTAS,
	ensure_ingresos_item_group_tree,
)
from club_management.members.test_helpers import MembersTestCase
from club_management.setup.icdpe_company import resolve_icdpe_company


class TestCleanupResidualItemGroups(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		try:
			resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("All Item Groups ausente")

	def _ensure_flat_group(self, name: str) -> None:
		if frappe.db.exists("Item Group", name):
			return
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": DEFAULT_ITEM_GROUP_ROOT,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)

	def _ensure_item(self, code: str, group: str, *, disabled: int = 1) -> None:
		if frappe.db.exists("Item", code):
			frappe.db.set_value("Item", code, "item_group", group)
			frappe.db.set_value("Item", code, "disabled", disabled)
			return
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"is_stock_item": 0,
				"disabled": disabled,
			}
		).insert(ignore_permissions=True)

	def test_finanzas_egresos_residual_se_limpia(self) -> None:
		ensure_egresos_item_group_tree()
		self._ensure_flat_group(RESIDUAL_FINANZAS_EGRESOS)
		self._ensure_item("ICDPE-FIN-SUELDOS", RESIDUAL_FINANZAS_EGRESOS, disabled=1)

		run_cleanup_residual_item_groups()
		run_cleanup_residual_item_groups()

		self.assertEqual(
			frappe.db.get_value("Item", "ICDPE-FIN-SUELDOS", "item_group"),
			GROUP_REMUNERACIONES,
		)
		self.assertEqual(int(frappe.db.get_value("Item", "ICDPE-FIN-SUELDOS", "disabled") or 0), 1)
		self.assertFalse(frappe.db.exists("Item Group", RESIDUAL_FINANZAS_EGRESOS))

	def test_cuotas_sociales_residual_a_hoja_canonica(self) -> None:
		ensure_ingresos_item_group_tree()
		# Solo crear residual si el name canónico es distinto (case/accents).
		if RESIDUAL_CUOTAS_SOCIALES == LEAF_CUOTAS:
			self.skipTest("Nombres residual y canónico coinciden")
		self._ensure_flat_group(RESIDUAL_CUOTAS_SOCIALES)
		code = "TEST-CUOTA-RESIDUAL-CLEAN"
		self._ensure_item(code, RESIDUAL_CUOTAS_SOCIALES, disabled=1)

		run_cleanup_residual_item_groups()

		self.assertEqual(frappe.db.get_value("Item", code, "item_group"), LEAF_CUOTAS)
		self.assertFalse(frappe.db.exists("Item Group", RESIDUAL_CUOTAS_SOCIALES))
		self.assertTrue(frappe.db.exists("Item Group", LEAF_CUOTAS))
