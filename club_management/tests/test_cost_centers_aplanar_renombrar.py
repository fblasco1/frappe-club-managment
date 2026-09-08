"""Tests aplanar/renombrar Cost Centers ICDPE (spec cost_centers_aplanar_renombrar.md)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.setup.flatten_rename_icdpe_cost_centers import (
	COST_CENTER_RENAME_MAP,
	MAIN_CC,
	run_flatten_rename_icdpe_cost_centers,
)
from club_management.setup.icdpe_company import COMPANY_ABBR, resolve_icdpe_company


class TestCostCentersAplanarRenombrar(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		try:
			self.company = resolve_icdpe_company()
		except Exception:
			self.skipTest("Company ICDPE no configurada")
		from club_management.setup.flatten_rename_icdpe_cost_centers import (
			_company_root_cost_center,
		)

		try:
			self.root = _company_root_cost_center(self.company)
		except Exception:
			self.skipTest("Sin Cost Center raíz ICDPE")

	def test_mapa_cubre_futbol_y_basquet(self) -> None:
		pairs = dict(COST_CENTER_RENAME_MAP)
		self.assertEqual(pairs[f"Deportes - Futbol - {COMPANY_ABBR}"], f"Futbol - {COMPANY_ABBR}")
		self.assertEqual(pairs[f"Deportes - Basquet - {COMPANY_ABBR}"], f"Basquet - {COMPANY_ABBR}")

	def test_flatten_reparent_y_rename_idempotente(self) -> None:
		if not frappe.db.exists("Cost Center", MAIN_CC) and not frappe.db.exists(
			"Cost Center", f"Futbol - {COMPANY_ABBR}"
		):
			# Sitio sin árbol ICDPE importado
			if not frappe.db.exists("Cost Center", f"Deportes - Futbol - {COMPANY_ABBR}"):
				self.skipTest("Sin CC Futbol (viejo ni nuevo) en el sitio")

		run_flatten_rename_icdpe_cost_centers()
		run_flatten_rename_icdpe_cost_centers()

		# Hojas cortas existen
		self.assertTrue(frappe.db.exists("Cost Center", f"Futbol - {COMPANY_ABBR}"))
		self.assertEqual(
			frappe.db.get_value("Cost Center", f"Futbol - {COMPANY_ABBR}", "cost_center_name"),
			"Futbol",
		)
		self.assertEqual(
			frappe.db.get_value("Cost Center", f"Futbol - {COMPANY_ABBR}", "parent_cost_center"),
			f"Deportes - {COMPANY_ABBR}",
		)

		# Áreas bajo raíz, no bajo Main
		for area in (
			f"Deportes - {COMPANY_ABBR}",
			f"Actividades - {COMPANY_ABBR}",
			f"Administración - {COMPANY_ABBR}",
		):
			if not frappe.db.exists("Cost Center", area):
				continue
			self.assertEqual(
				frappe.db.get_value("Cost Center", area, "parent_cost_center"),
				self.root,
				msg=area,
			)

		if frappe.db.exists("Cost Center", MAIN_CC):
			self.assertEqual(frappe.db.count("Cost Center", {"parent_cost_center": MAIN_CC}), 0)
			self.assertEqual(int(frappe.db.get_value("Cost Center", MAIN_CC, "disabled") or 0), 1)

	def test_crossfit_funcional_bajo_fitness(self) -> None:
		run_flatten_rename_icdpe_cost_centers()
		for leaf in (f"CrossFit - {COMPANY_ABBR}", f"Funcional - {COMPANY_ABBR}"):
			if not frappe.db.exists("Cost Center", leaf):
				self.skipTest(f"Falta {leaf}")
			self.assertEqual(
				frappe.db.get_value("Cost Center", leaf, "parent_cost_center"),
				f"Fitness - {COMPANY_ABBR}",
				msg=leaf,
			)

	def test_admin_y_cuotas_primeros_bajo_raiz(self) -> None:
		run_flatten_rename_icdpe_cost_centers()
		children = frappe.get_all(
			"Cost Center",
			filters={"parent_cost_center": self.root, "disabled": 0},
			pluck="name",
			order_by="lft asc",
		)
		self.assertGreaterEqual(len(children), 2)
		self.assertEqual(children[0], f"Administración - {COMPANY_ABBR}")
		self.assertEqual(children[1], f"Cuotas Sociales - {COMPANY_ABBR}")

	def test_rename_actualiza_item_default(self) -> None:
		old = f"Deportes - Voley - {COMPANY_ABBR}"
		new = f"Voley - {COMPANY_ABBR}"
		# Si ya migró, usamos new; si no, old
		cc_before = old if frappe.db.exists("Cost Center", old) else new
		if not frappe.db.exists("Cost Center", cc_before):
			self.skipTest("Sin CC Voley en el sitio")

		code = "TEST-CC-APLANAR-VOLEY"
		if frappe.db.exists("Item", code):
			frappe.delete_doc("Item", code, force=1, ignore_permissions=True)

		group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_name": code,
				"item_group": group,
				"is_stock_item": 0,
				"is_sales_item": 1,
				"item_defaults": [
					{"company": self.company, "selling_cost_center": cc_before},
				],
			}
		).insert(ignore_permissions=True)

		run_flatten_rename_icdpe_cost_centers()

		row_cc = frappe.db.get_value(
			"Item Default",
			{"parent": code, "company": self.company},
			"selling_cost_center",
		)
		self.assertEqual(row_cc, new)
		self.assertTrue(frappe.db.exists("Cost Center", new))
