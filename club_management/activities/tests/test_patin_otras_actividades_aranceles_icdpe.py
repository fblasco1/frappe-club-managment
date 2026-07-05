"""Tests aranceles mensuales patín y otras actividades ICDPE."""

from __future__ import annotations

import frappe

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	ITEM_DANZA,
	ITEM_GIMNASIA_2_CLASES,
	ITEM_GYM_SOCIO,
	ITEM_RITMOS_LATINOS,
	ITEM_TAEKWONDO,
)
from club_management.activities.data.patin_aranceles_icdpe import (
	ITEM_PATIN_AVANZADO,
	ITEM_PATIN_MINI,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.test_helpers import MembersTestCase


class TestPatinOtrasActividadesArancelesIcdpe(MembersTestCase):
	def test_seed_patin_avanzado_equipo_b(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		patin = frappe.db.get_value("Actividad", {"titulo": "Patin Artistico"}, "name")
		equipo = f"{patin} / Patin Avanzado / B"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_PATIN_AVANZADO)

	def test_seed_patin_mini(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		patin = frappe.db.get_value("Actividad", {"titulo": "Patin Artistico"}, "name")
		equipo = f"{patin} / Patin Mini / Patin Mini"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_PATIN_MINI)

	def test_seed_patin_adulto(self) -> None:
		from club_management.activities.data.patin_aranceles_icdpe import ITEM_PATIN_ADULTO

		seed_estructura_actividades_completa(crear_equipos=True)
		patin = frappe.db.get_value("Actividad", {"titulo": "Patin Artistico"}, "name")
		grupo = f"{patin} / Adulto"
		self.assertTrue(frappe.db.get_value("Grupo Actividad", grupo, "habilitada"))
		equipo = f"{grupo} / Adulto"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_PATIN_ADULTO)
		self.assertEqual(frappe.db.get_value("Item", ITEM_PATIN_ADULTO, "standard_rate"), 26500)

	def test_seed_gimnasia_dos_clases(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		ga = frappe.db.get_value("Actividad", {"titulo": "Gimnasia Artistica"}, "name")
		grupo = f"{ga} / 2 Clases por Semana"
		self.assertTrue(frappe.db.get_value("Grupo Actividad", grupo, "habilitada"))
		equipo = f"{grupo} / 2 Clases por Semana"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_GIMNASIA_2_CLASES)

	def test_seed_gimnasio_socio(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		gym = frappe.db.get_value("Actividad", {"titulo": "Gimnasio Fitness"}, "name")
		equipo = f"{gym} / Socio / Socio"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_GYM_SOCIO)
		self.assertEqual(frappe.db.get_value("Item", ITEM_GYM_SOCIO, "standard_rate"), 22000)

	def test_seed_iniciacion_dos_clases(self) -> None:
		from club_management.activities.data.otras_actividades_aranceles_icdpe import (
			ITEM_INICIACION_2_CLASES,
		)

		seed_estructura_actividades_completa(crear_equipos=True)
		ini = frappe.db.get_value("Actividad", {"titulo": "Iniciacion Deportiva"}, "name")
		self.assertTrue(frappe.db.get_value("Actividad", ini, "usa_grupos"))
		equipo = f"{ini} / 2 Clases por Semana / 2 Clases por Semana"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_INICIACION_2_CLASES)

	def test_catalogo_actividades_planas_con_item(self) -> None:
		from club_management.patches.v1_0.sync_patin_otras_actividades_aranceles_icdpe import execute

		execute()
		for titulo, item in (
			("Danza", ITEM_DANZA),
			("Taekwondo", ITEM_TAEKWONDO),
			("Ritmos Latinos", ITEM_RITMOS_LATINOS),
		):
			name = frappe.db.get_value("Actividad", {"titulo": titulo}, "name")
			self.assertFalse(frappe.db.get_value("Actividad", name, "usa_grupos"))
			self.assertEqual(frappe.db.get_value("Actividad", name, "item"), item)

	def test_catalogo_incluye_boxeo_y_yoga(self) -> None:
		from club_management.patches.v1_0.sync_patin_otras_actividades_aranceles_icdpe import execute

		execute()
		self.assertTrue(frappe.db.exists("Actividad", {"titulo": "Boxeo", "habilitada": 1}))
		self.assertTrue(frappe.db.exists("Actividad", {"titulo": "Yoga", "habilitada": 1}))
		self.assertTrue(frappe.db.get_value("Actividad", {"titulo": "Boxeo"}, "usa_grupos"))
