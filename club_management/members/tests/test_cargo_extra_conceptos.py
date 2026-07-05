"""Tests conceptos sugeridos para cargo extra (spec cargo_extra_conceptos_y_facturacion.md)."""

from __future__ import annotations

import frappe

from club_management.members.services.cargo_extra_conceptos import (
	item_codes_cargo_extra_socio,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio

GRUPO_GENERAL = "ICDPE / Cargos varios"
GRUPO_TEST_ITEMS = "Test Cargo Extra Items"


class TestCargoExtraConceptos(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._company = self._resolve_company()
		if not self._company:
			self.skipTest("No hay Company configurada para Item Default")
		self._cc_a = self._ensure_cost_center("CC Cargo Extra A")
		self._cc_b = self._ensure_cost_center("CC Cargo Extra B")
		self._ensure_item_group(GRUPO_TEST_ITEMS)
		self._arancel_a = self._ensure_item("TEST-ARANCEL-A", self._cc_a, item_group=GRUPO_TEST_ITEMS)
		self._federativa_a = self._ensure_item("TEST-FEDERATIVA-A", self._cc_a, item_group=GRUPO_TEST_ITEMS)
		self._arancel_b = self._ensure_item("TEST-ARANCEL-B", self._cc_b, item_group=GRUPO_TEST_ITEMS)
		self._federativa_b = self._ensure_item("TEST-FEDERATIVA-B", self._cc_b, item_group=GRUPO_TEST_ITEMS)
		self._multa = self._ensure_item("TEST-MULTA-GENERAL", None, item_group=GRUPO_GENERAL)
		for item_code, titulo in (
			(self._arancel_a, "Fixture arancel A"),
			(self._arancel_b, "Fixture arancel B"),
		):
			if not frappe.db.exists("Actividad", {"item": item_code}):
				frappe.get_doc(
					{
						"doctype": "Actividad",
						"titulo": titulo,
						"item": item_code,
						"habilitada": 0,
					}
				).insert(ignore_permissions=True)

	def _resolve_company(self) -> str | None:
		"""Empresa cuyo almacén por defecto evita el choque de validación."""
		default_wh = frappe.db.get_single_value("Stock Settings", "default_warehouse")
		if default_wh:
			company = frappe.db.get_value("Warehouse", default_wh, "company")
			if company:
				return company
		return frappe.db.get_value("Company", {}, "name")

	def _ensure_item_group(self, name: str) -> str:
		if frappe.db.exists("Item Group", name):
			return name
		root = frappe.db.get_value("Item Group", {"is_group": 1}, "name") or "All Item Groups"
		frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": name,
				"parent_item_group": root,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		return name

	def _ensure_cost_center(self, name: str) -> str:
		existing = frappe.db.get_value(
			"Cost Center", {"cost_center_name": name, "company": self._company}, "name"
		)
		if existing:
			return existing
		parent = frappe.db.get_value(
			"Cost Center", {"company": self._company, "is_group": 1}, "name"
		)
		doc = frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": name,
				"parent_cost_center": parent,
				"company": self._company,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def _ensure_item(
		self,
		code: str,
		cost_center: str | None,
		*,
		item_group: str | None = None,
	) -> str:
		group = item_group or frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
		if item_group:
			group = self._ensure_item_group(item_group)
		if frappe.db.exists("Item", code):
			frappe.db.delete("Item Default", {"parent": code})
			if cost_center:
				frappe.get_doc(
					{
						"doctype": "Item Default",
						"parent": code,
						"parenttype": "Item",
						"parentfield": "item_defaults",
						"company": self._company,
						"selling_cost_center": cost_center,
					}
				).insert(ignore_permissions=True)
			if item_group:
				frappe.db.set_value("Item", code, "item_group", item_group)
			return code
		payload: dict = {
			"doctype": "Item",
			"item_code": code,
			"item_name": code,
			"item_group": group,
			"is_stock_item": 0,
			"is_sales_item": 1,
		}
		if cost_center:
			payload["item_defaults"] = [
				{"company": self._company, "selling_cost_center": cost_center}
			]
		frappe.get_doc(payload).insert(ignore_permissions=True)
		return code

	def _socio_con_inscripcion(self, **kwargs):
		socio = insert_socio(**kwargs)
		cambiar_estado(socio.name, "Activo", motivo="Test conceptos")
		actividad = frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": "Actividad Cargo Extra A",
				"item": self._arancel_a,
				"habilitada": 1,
			}
		)
		actividad.insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": actividad.name,
				"estado": "Activa",
				"fecha_inscripcion": "2026-06-01",
			}
		).insert(ignore_permissions=True)
		return socio

	def test_conceptos_incluyen_federativa_de_actividad_inscripta(self) -> None:
		socio = self._socio_con_inscripcion(dni="75002001", email="conc.act@example.com")
		codes = item_codes_cargo_extra_socio(socio.name)
		self.assertIn(self._federativa_a, codes)

	def test_conceptos_excluyen_arancel_mensual(self) -> None:
		socio = self._socio_con_inscripcion(dni="75002002", email="conc.aran@example.com")
		codes = item_codes_cargo_extra_socio(socio.name)
		self.assertNotIn(self._arancel_a, codes)

	def test_conceptos_excluyen_otra_actividad_no_inscripta(self) -> None:
		socio = self._socio_con_inscripcion(dni="75002003", email="conc.otra@example.com")
		codes = item_codes_cargo_extra_socio(socio.name)
		self.assertNotIn(self._arancel_b, codes)
		self.assertNotIn(self._federativa_b, codes)

	def test_conceptos_generales_disponibles_sin_inscripciones(self) -> None:
		socio = insert_socio(dni="75002004", email="conc.gen@example.com")
		cambiar_estado(socio.name, "Activo", motivo="Test conceptos")
		codes = item_codes_cargo_extra_socio(socio.name)
		self.assertIn(self._multa, codes)
