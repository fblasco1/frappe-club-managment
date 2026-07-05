"""Tests aranceles mensuales básquet ICDPE."""

from __future__ import annotations

import frappe

from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_ESCUELITA,
	ITEM_FORMATIVAS_AZUL,
	ITEM_MINIBASQUET,
)
from club_management.activities.services.basquet_icdpe_items import retire_packs_clases_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.inscripcion_socio import resolve_item_arancel_inscripcion
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestBasquetArancelesIcdpe(MembersTestCase):
	def test_seed_basquet_masculino_azul_u13_minibasquet(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		equipo = f"{basquet} / Masculino / Azul / U13"
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo))
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_MINIBASQUET)

	def test_seed_basquet_masculino_azul_u15_formativas_azul(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		equipo = f"{basquet} / Masculino / Azul / U15"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FORMATIVAS_AZUL)

	def test_seed_basquet_mixto_escuela(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		equipo = f"{basquet} / Mixto / Escuela / U7 / U9"
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo))
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_ESCUELITA)

	def test_resolve_arancel_desde_equipo(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		grupo = f"{basquet} / Mixto / Escuela"
		equipo = f"{grupo} / U7 / U9"
		if not frappe.db.exists("Item", ITEM_ESCUELITA):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": ITEM_ESCUELITA,
					"item_name": "Escuelita",
					"item_group": "All Item Groups",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Equipo Actividad", equipo, "item", ITEM_ESCUELITA)

		socio = insert_socio(dni="72001001", email="basquet.eq@example.com", estado="Activo")
		from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones

		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": basquet, "grupo": grupo, "equipo": equipo}],
			activar=False,
		)
		ins_name = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "equipo_actividad": equipo},
			"name",
		)
		self.assertEqual(resolve_item_arancel_inscripcion(ins_name), ITEM_ESCUELITA)

	def test_retire_packs_clases(self) -> None:
		code = "ICDPE-PACKS-CLASES-test-retire"
		if not frappe.db.exists("Item", code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": code,
					"item_name": "Pack test",
					"item_group": "All Item Groups",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		retired = retire_packs_clases_items()
		self.assertIn(code, retired)
		self.assertEqual(frappe.db.get_value("Item", code, "disabled"), 1)
