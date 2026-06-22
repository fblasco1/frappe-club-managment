"""Tests aranceles mensuales vóley y fútbol ICDPE."""

from __future__ import annotations

import frappe

from club_management.activities.data.futbol_aranceles_icdpe import (
	GRUPO_FUTBOL_ESCUELITA,
	ITEM_FUTBOL_FAFI,
	ITEM_FUTBOL_TABI_B,
)
from club_management.activities.data.voley_aranceles_icdpe import (
	ITEM_VOLEY_ESCUELITA_MINIVOLEY,
	ITEM_VOLEY_TIRA_21500,
	ITEM_VOLEY_TIRA_30500,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.test_helpers import MembersTestCase


class TestVoleyFutbolArancelesIcdpe(MembersTestCase):
	def test_seed_voley_tira_u12(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		equipo = f"{vf} / Tira / U12"
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo))
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_VOLEY_TIRA_21500)

	def test_seed_voley_superior_a(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		equipo = f"{vf} / Tira / Superior A"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_VOLEY_TIRA_30500)

	def test_seed_voley_escuelita_minivoley(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		equipo = f"{vf} / Escuelita Minivoley / Escuelita Minivoley"
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", equipo, "item"),
			ITEM_VOLEY_ESCUELITA_MINIVOLEY,
		)

	def test_seed_futbol_fafi_2016(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		equipo = f"{futbol} / FAFI / 2016"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FUTBOL_FAFI)

	def test_seed_futbol_tabi_b(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		equipo = f"{futbol} / TABI B / 2018/2019"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FUTBOL_TABI_B)

	def test_futbol_escuelita_es_tabi_b(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		self.assertEqual(GRUPO_FUTBOL_ESCUELITA, "TABI B")
		self.assertTrue(frappe.db.get_value("Grupo Actividad", f"{futbol} / TABI B", "habilitada"))
		self.assertFalse(frappe.db.exists("Grupo Actividad", f"{futbol} / Escuelita"))
		equipo = f"{futbol} / TABI B / 2020/2021"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FUTBOL_TABI_B)

	def test_legacy_voley_grupos_deshabilitados(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		self.assertFalse(frappe.db.get_value("Grupo Actividad", f"{vf} / Primera Division", "habilitada"))
		self.assertFalse(frappe.db.get_value("Grupo Actividad", f"{vf} / Segunda Division", "habilitada"))
