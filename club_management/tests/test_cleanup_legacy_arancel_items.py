"""Tests limpieza Shoe + aranceles ARANCEL-MENSUAL disabled (spec cleanup_legacy_arancel_items)."""

from __future__ import annotations

import frappe

from club_management.finance.setup.cleanup_legacy_arancel_items import (
	DEMO_SHOE_ITEM_CODE,
	run_cleanup_legacy_arancel_items,
)
from club_management.finance.setup.icdpe_finance_items import DEFAULT_ITEM_GROUP_ROOT
from club_management.members.test_helpers import MembersTestCase


def _leaf_group() -> str:
	for candidate in ("Products", "Services"):
		if frappe.db.exists("Item Group", candidate):
			if int(frappe.db.get_value("Item Group", candidate, "is_group") or 0) == 0:
				return candidate
	# cualquier hoja
	name = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
	if name:
		return name
	raise frappe.ValidationError("No hay Item Group hoja")


class TestCleanupLegacyArancelItems(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		if not frappe.db.exists("DocType", "Item"):
			self.skipTest("ERPNext no instalado")
		if not frappe.db.exists("Item Group", DEFAULT_ITEM_GROUP_ROOT):
			self.skipTest("All Item Groups ausente")

	def test_deshabilita_arancel_mensual_habilitado(self) -> None:
		from club_management.finance.setup.cleanup_legacy_arancel_items import (
			disable_enabled_legacy_arancel_mensual,
		)

		group = _leaf_group()
		code = "ICDPE-ARANCEL-MENSUAL-BOXEO-1_VEZ"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": "Arancel Mensual Boxeo - 1 Vez",
					"item_group": group,
					"is_stock_item": 0,
					"disabled": 0,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", code, "disabled", 0)

		retired = disable_enabled_legacy_arancel_mensual()
		self.assertIn(code, retired)
		self.assertEqual(int(frappe.db.get_value("Item", code, "disabled") or 0), 1)

	def test_deshabilita_shoe_demo(self) -> None:
		group = _leaf_group()
		if not frappe.db.exists("Item", DEMO_SHOE_ITEM_CODE):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": DEMO_SHOE_ITEM_CODE,
					"item_name": DEMO_SHOE_ITEM_CODE,
					"item_group": group,
					"is_stock_item": 0,
					"disabled": 0,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", DEMO_SHOE_ITEM_CODE, "disabled", 0)

		run_cleanup_legacy_arancel_items()

		self.assertEqual(int(frappe.db.get_value("Item", DEMO_SHOE_ITEM_CODE, "disabled") or 0), 1)

	def test_elimina_arancel_mensual_disabled_sin_factura(self) -> None:
		group = _leaf_group()
		code = "ICDPE-ARANCEL-MENSUAL-CLEANUP-UNIT-LEGACY"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"is_stock_item": 0,
				"disabled": 1,
			}
		).insert(ignore_permissions=True)

		run_cleanup_legacy_arancel_items()

		self.assertFalse(frappe.db.exists("Item", code))

	def test_no_elimina_arancel_mensual_disabled_con_si(self) -> None:
		from unittest.mock import patch

		group = _leaf_group()
		code = "ICDPE-ARANCEL-MENSUAL-CLEANUP-UNIT-KEEP-SI"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)

		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"is_stock_item": 0,
				"disabled": 1,
			}
		).insert(ignore_permissions=True)

		with patch(
			"club_management.finance.setup.cleanup_legacy_arancel_items._invoice_refs",
			return_value=1,
		):
			result = run_cleanup_legacy_arancel_items()

		self.assertTrue(frappe.db.exists("Item", code))
		self.assertTrue(any(code in s for s in result.get("aranceles", {}).get("skipped", [])))

	def test_remapea_link_antes_de_borrar(self) -> None:
		from club_management.finance.setup.cleanup_legacy_arancel_items import (
			LEGACY_ARANCEL_TO_CANONICAL,
			remape_legacy_arancel_links,
		)

		if not frappe.db.exists("DocType", "Grupo Actividad"):
			self.skipTest("Grupo Actividad ausente")
		if not frappe.get_meta("Grupo Actividad").has_field("item"):
			self.skipTest("Grupo Actividad.item ausente")

		legacy, canonical = next(iter(LEGACY_ARANCEL_TO_CANONICAL.items()))
		group = _leaf_group()
		for code, disabled in ((legacy, 1), (canonical, 0)):
			if not frappe.db.exists("Item", code):
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

		# usar un grupo existente o saltar si no hay ninguno con campo editable
		grupos = frappe.get_all("Grupo Actividad", pluck="name", limit=1)
		if not grupos:
			self.skipTest("Sin Grupo Actividad para remap")
		gname = grupos[0]
		prev = frappe.db.get_value("Grupo Actividad", gname, "item")
		frappe.db.set_value("Grupo Actividad", gname, "item", legacy, update_modified=False)

		try:
			result = remape_legacy_arancel_links()
			self.assertEqual(frappe.db.get_value("Grupo Actividad", gname, "item"), canonical)
			self.assertTrue(any(legacy in r and canonical in r for r in result["remapped"]))
		finally:
			frappe.db.set_value("Grupo Actividad", gname, "item", prev, update_modified=False)
