"""Tests aranceles mensuales vóley y fútbol ICDPE."""

from __future__ import annotations

import frappe

from club_management.activities.data.arancel_item_spec import format_arancel_mensual_item_name
from club_management.activities.data.futbol_aranceles_icdpe import (
	GRUPO_FUTBOL_ESCUELITA,
	ITEM_FUTBOL_FAFI,
	ITEM_FUTBOL_TABI_B,
)
from club_management.activities.data.voley_aranceles_icdpe import (
	ITEM_VOLEY_ESCUELA,
	ITEM_VOLEY_FEDERADO,
	VOLEY_ITEM_SPECS,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.inscripcion_socio import (
	inscribir_socio_selecciones,
	resolve_item_arancel_inscripcion,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestVoleyFutbolArancelesIcdpe(MembersTestCase):
	def test_voley_solo_dos_aranceles_canonico(self) -> None:
		codes = {s.item_code for s in VOLEY_ITEM_SPECS}
		self.assertEqual(codes, {ITEM_VOLEY_ESCUELA, ITEM_VOLEY_FEDERADO})
		by_code = {s.item_code: s for s in VOLEY_ITEM_SPECS}
		self.assertEqual(
			by_code[ITEM_VOLEY_ESCUELA].item_name,
			format_arancel_mensual_item_name("VOLEY", "ESCUELA"),
		)
		self.assertEqual(
			by_code[ITEM_VOLEY_FEDERADO].item_name,
			format_arancel_mensual_item_name("VOLEY", "FEDERADO"),
		)
		self.assertEqual(by_code[ITEM_VOLEY_ESCUELA].rate, 21500.0)
		self.assertEqual(by_code[ITEM_VOLEY_FEDERADO].rate, 30500.0)

	def test_seed_voley_tira_u12_federado(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		grupo = f"{vf} / Tira"
		equipo = f"{grupo} / U12"
		self.assertTrue(frappe.db.exists("Equipo Actividad", equipo))
		self.assertEqual(frappe.db.get_value("Grupo Actividad", grupo, "item"), ITEM_VOLEY_FEDERADO)
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_VOLEY_FEDERADO)

	def test_seed_voley_superior_a(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		equipo = f"{vf} / Tira / Superior A"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_VOLEY_FEDERADO)

	def test_seed_voley_escuelita_minivoley(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		grupo = f"{vf} / Escuelita Minivoley"
		equipo = f"{grupo} / Escuelita Minivoley"
		self.assertEqual(frappe.db.get_value("Grupo Actividad", grupo, "item"), ITEM_VOLEY_ESCUELA)
		self.assertEqual(
			frappe.db.get_value("Equipo Actividad", equipo, "item"),
			ITEM_VOLEY_ESCUELA,
		)

	def test_seed_voley_escuela_adolescente(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		grupo = f"{vf} / Escuela Adolescente"
		self.assertEqual(frappe.db.get_value("Grupo Actividad", grupo, "item"), ITEM_VOLEY_ESCUELA)

	def test_voley_tira_sin_equipo_usa_grupo_federado(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		grupo = f"{vf} / Tira"
		socio = insert_socio(dni="72001001", email="voley.tira.grupo@example.com", estado="Activo")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": vf, "grupo": grupo}],
			activar=False,
		)
		ins_name = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "grupo_actividad": grupo},
			"name",
		)
		self.assertEqual(resolve_item_arancel_inscripcion(ins_name), ITEM_VOLEY_FEDERADO)

	def test_seed_futbol_fafi_2016(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		grupo = f"{futbol} / FAFI"
		equipo = f"{grupo} / 2016"
		self.assertEqual(frappe.db.get_value("Grupo Actividad", grupo, "item"), ITEM_FUTBOL_FAFI)
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FUTBOL_FAFI)

	def test_futbol_fafi_sin_equipo_usa_grupo(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		futbol = frappe.db.get_value("Actividad", {"titulo": "Futbol"}, "name")
		grupo = f"{futbol} / FAFI"
		socio = insert_socio(dni="72001002", email="futbol.fafi.grupo@example.com", estado="Activo")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": futbol, "grupo": grupo}],
			activar=False,
		)
		ins_name = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "grupo_actividad": grupo},
			"name",
		)
		self.assertEqual(resolve_item_arancel_inscripcion(ins_name), ITEM_FUTBOL_FAFI)

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
		# Legacy «Escuelita» puede existir deshabilitado; no debe estar habilitado.
		self.assertFalse(
			frappe.db.get_value("Grupo Actividad", f"{futbol} / Escuelita", "habilitada")
		)
		equipo = f"{futbol} / TABI B / 2020/2021"
		self.assertEqual(frappe.db.get_value("Equipo Actividad", equipo, "item"), ITEM_FUTBOL_TABI_B)

	def test_legacy_voley_grupos_deshabilitados(self) -> None:
		seed_estructura_actividades_completa(crear_equipos=True)
		vf = frappe.db.get_value("Actividad", {"titulo": "Voley Femenino"}, "name")
		self.assertFalse(frappe.db.get_value("Grupo Actividad", f"{vf} / Primera Division", "habilitada"))
		self.assertFalse(frappe.db.get_value("Grupo Actividad", f"{vf} / Segunda Division", "habilitada"))
