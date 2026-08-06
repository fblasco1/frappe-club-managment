"""Tests del seed de estructura completa."""

from __future__ import annotations

import frappe

from club_management.activities.data.estructura_actividades_club import (
	CATEGORIAS_EQUIPO,
	ESTRUCTURA_CON_GRUPOS,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.test_helpers import MembersTestCase


class TestEstructuraActividadesSeed(MembersTestCase):
	def test_seed_crea_actividades_grupos_y_equipos(self) -> None:
		result = seed_estructura_actividades_completa(crear_equipos=True)

		self.assertGreaterEqual(result["actividades"], 16)
		expected_grupos = sum(len(e.grupos) for e in ESTRUCTURA_CON_GRUPOS)
		self.assertEqual(result["grupos"], expected_grupos)

		self.assertTrue(frappe.db.exists("Actividad", "Zumba"))
		self.assertTrue(frappe.db.exists("Actividad", "Ritmos Latinos"))
		self.assertFalse(frappe.db.get_value("Actividad", "Zumba", "usa_grupos"))

		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		self.assertTrue(frappe.db.get_value("Actividad", basquet, "usa_grupos"))
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{basquet} / Masculino / Azul"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{basquet} / Masculino / Azul / U11"))
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{basquet} / Mixto / Escuela"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{basquet} / Mixto / Escuela / U7 / U9"))

		equipos_basquet_azul = frappe.db.count(
			"Equipo Actividad",
			{"grupo_actividad": f"{basquet} / Masculino / Azul", "habilitada": 1},
		)
		self.assertEqual(equipos_basquet_azul, 6)

		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{vf} / Tira"))
		self.assertEqual(
			frappe.db.count("Equipo Actividad", {"grupo_actividad": f"{vf} / Tira", "habilitada": 1}),
			10,
		)

		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{futbol} / FAFI"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{futbol} / TABI B / 2020/2021"))

	def test_seed_grupo_item_no_basquet_y_basquet_sin_item(self) -> None:
		from club_management.activities.data.futbol_aranceles_icdpe import ITEM_FUTBOL_FAFI
		from club_management.activities.data.voley_aranceles_icdpe import ITEM_VOLEY_TIRA_30500

		seed_estructura_actividades_completa(crear_equipos=True)
		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		azul = f"{basquet} / Masculino / Azul"
		self.assertFalse(frappe.db.get_value("Grupo Actividad", azul, "item"))

		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		self.assertEqual(
			frappe.db.get_value("Grupo Actividad", f"{vf} / Tira", "item"),
			ITEM_VOLEY_TIRA_30500,
		)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		self.assertEqual(
			frappe.db.get_value("Grupo Actividad", f"{futbol} / FAFI", "item"),
			ITEM_FUTBOL_FAFI,
		)
