"""Tests vinculación roster básquet (spec vinculacion_basquet_roster.md)."""

from __future__ import annotations

import frappe

from club_management.activities.services.basquet_roster_link import (
	map_basquet_seleccion,
	normalize_roster_dni,
	parse_jugadores_xlsx,
	resolve_seleccion_basquet,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestBasquetRosterMapping(MembersTestCase):
	def test_map_u13_azul(self) -> None:
		sel = map_basquet_seleccion("U13", "Azul")
		self.assertEqual(sel["actividad"], "Basquet")
		self.assertEqual(sel["grupo"], "Masculino / Azul")
		self.assertEqual(sel["equipo"], "U13")

	def test_map_u7_escuelita(self) -> None:
		sel = map_basquet_seleccion("U7", "Escuelita")
		self.assertEqual(sel["actividad"], "Basquet")
		self.assertEqual(sel["grupo"], "Mixto / Escuela")
		self.assertEqual(sel["equipo"], "U7 / U9")

	def test_map_u15_femenino(self) -> None:
		sel = map_basquet_seleccion("U15", "Femenino")
		self.assertEqual(sel["actividad"], "Basquet")
		self.assertEqual(sel["grupo"], "Femenino / Formativa")
		self.assertEqual(sel["equipo"], "U15")

	def test_map_u13_amarillo(self) -> None:
		sel = map_basquet_seleccion("U13", "Amarillo")
		self.assertEqual(sel["grupo"], "Masculino / Amarillo")

	def test_map_mayor_mayor_superior_flex(self) -> None:
		sel = map_basquet_seleccion("MAYOR", "MAYOR")
		self.assertEqual(sel["grupo"], "Masculino / Flex")
		self.assertEqual(sel["equipo"], "Superior C")

	def test_normalize_dni_scientific(self) -> None:
		self.assertEqual(normalize_roster_dni("5.6175501E7"), "56175501")

	def test_resolve_seleccion_requires_seed(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		sel = map_basquet_seleccion("U13", "Azul")
		resolved = resolve_seleccion_basquet(sel)
		self.assertTrue(frappe.db.exists("Equipo Actividad", resolved["equipo_actividad"]))


class TestBasquetRosterLinkSocio(MembersTestCase):
	def test_vincular_socio_por_dni(self) -> None:
		from club_management.activities.services.basquet_roster_link import (
			vincular_basquet_socio,
		)

		seed_estructura_actividades_completa(crear_equipos=True)
		socio = insert_socio(dni="52417804", email="roster.u13@example.com", estado="Activo")
		result = vincular_basquet_socio(
			socio.name,
			categoria="U13",
			equipo="Azul",
			dry_run=False,
		)
		self.assertEqual(result["status"], "ok")
		equipo_name = result["equipo_actividad"]
		self.assertTrue(equipo_name)
		self.assertTrue(
			frappe.db.exists(
				"Inscripcion Actividad",
				{"socio": socio.name, "equipo_actividad": equipo_name, "estado": "Activa"},
			)
		)
		self.assertIn("Basquet", frappe.db.get_value("Socio", socio.name, "actividad") or "")
