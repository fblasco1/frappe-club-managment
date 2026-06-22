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

		self.assertGreaterEqual(result["actividades"], 18)
		expected_grupos = sum(len(e.grupos) for e in ESTRUCTURA_CON_GRUPOS)
		self.assertEqual(result["grupos"], expected_grupos)

		self.assertTrue(frappe.db.exists("Actividad", "Zumba"))
		self.assertTrue(frappe.db.exists("Actividad", "Ritmos Latinos"))
		self.assertFalse(frappe.db.get_value("Actividad", "Zumba", "usa_grupos"))

		bm = frappe.db.get_value("Actividad", {"titulo": "Basquet Masculino"}, "name")
		self.assertTrue(frappe.db.get_value("Actividad", bm, "usa_grupos"))
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{bm} / Tira Azul"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{bm} / Tira Azul / U11"))
		self.assertFalse(frappe.db.exists("Grupo Actividad", f"{bm} / Escuelita"))

		be = frappe.db.get_value("Actividad", {"titulo": "Basquet Escuelita"}, "name")
		self.assertTrue(frappe.db.get_value("Actividad", be, "usa_grupos"))
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{be} / Mixta"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{be} / Mixta / U7 / U9"))

		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{vf} / Tira"))
		self.assertEqual(
			frappe.db.count("Equipo Actividad", {"grupo_actividad": f"{vf} / Tira", "habilitada": 1}),
			10,
		)

		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		self.assertTrue(frappe.db.exists("Grupo Actividad", f"{futbol} / FAFI"))
		self.assertTrue(frappe.db.exists("Equipo Actividad", f"{futbol} / TABI B / 2020/2021"))

		equipos_bm_azul = frappe.db.count(
			"Equipo Actividad",
			{"grupo_actividad": f"{bm} / Tira Azul", "habilitada": 1},
		)
		self.assertEqual(equipos_bm_azul, 6)
