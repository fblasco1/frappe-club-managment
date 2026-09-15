"""Tests seed básquet unificado (spec basquet_estructura_unificada.md)."""

from __future__ import annotations

import frappe

from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_ESCUELITA,
	ITEM_FEMENINO_SUP,
	ITEM_FORMATIVAS_AZUL,
	ITEM_MINIBASQUET,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.test_helpers import MembersTestCase


class TestBasquetEstructuraUnificadaSeed(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		seed_estructura_actividades_completa(crear_equipos=True)
		self.basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		self.assertTrue(self.basquet)

	def test_actividad_unica_basquet_habilitada(self) -> None:
		self.assertTrue(frappe.db.get_value("Actividad", self.basquet, "usa_grupos"))
		self.assertTrue(frappe.db.get_value("Actividad", self.basquet, "habilitada"))
		for legacy in ("Basquet Masculino", "Basquet Escuelita", "Basquet Femenino"):
			if frappe.db.exists("Actividad", {"titulo": legacy}):
				self.assertFalse(frappe.db.get_value("Actividad", {"titulo": legacy}, "habilitada"))

	def test_grupos_masculinos_y_equipos(self) -> None:
		azul = f"{self.basquet} / Masculino / Azul"
		self.assertTrue(frappe.db.exists("Grupo Actividad", azul))
		self.assertEqual(
			frappe.db.count("Equipo Actividad", {"grupo_actividad": azul, "habilitada": 1}),
			6,
		)
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", f"{azul} / U13", "item"),
			ITEM_MINIBASQUET,
		)
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", f"{azul} / U15", "item"),
			ITEM_FORMATIVAS_AZUL,
		)
		amarillo = f"{self.basquet} / Masculino / Amarillo"
		self.assertTrue(frappe.db.exists("Grupo Actividad", amarillo))
		flex = f"{self.basquet} / Masculino / Flex"
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{flex} / Superior C"))

	def test_femenino_formativa_y_superior(self) -> None:
		formativa = f"{self.basquet} / Femenino / Formativa"
		superior = f"{self.basquet} / Femenino / Superior"
		self.assertTrue(frappe.db.exists("Grupo Actividad", formativa))
		self.assertTrue(frappe.db.exists("Grupo Actividad", superior))
		self.assertEqual(
			frappe.db.count("Equipo Actividad", {"grupo_actividad": formativa, "habilitada": 1}),
			5,
		)
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{formativa} / U15"))
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", f"{formativa} / U15", "item"),
			ITEM_ESCUELITA,
		)
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{superior} / Superior Fem"))
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", f"{superior} / Superior Fem", "item"),
			ITEM_FEMENINO_SUP,
		)

	def test_mixto_escuela(self) -> None:
		escuela = f"{self.basquet} / Mixto / Escuela"
		self.assertTrue(frappe.db.exists("Grupo Actividad", escuela))
		equipo = f"{escuela} / U7 / U9"
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo))
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_ESCUELITA)
