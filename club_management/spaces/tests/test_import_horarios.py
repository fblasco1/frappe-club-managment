"""Tests importación CSV horarios L–V."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.availability import build_horario_titulo
from club_management.spaces.import_horarios import (
	CANCHA_1,
	CANCHA_2,
	default_horarios_csv_path,
	default_horarios_sabado_csv_path,
	import_horarios_csv,
	import_horarios_sabado,
	load_csv_rows,
	map_espacio,
	match_actividad,
	parse_horario,
)


class TestImportHorariosParser(MembersTestCase):
	def test_parse_horario_variantes(self) -> None:
		self.assertEqual(parse_horario("08:15 A 12:15"), ("08:15:00", "12:15:00"))
		self.assertEqual(parse_horario("15 A 16"), ("15:00:00", "16:00:00"))
		self.assertEqual(parse_horario("18.30 A 19.30 HS"), ("18:30:00", "19:30:00"))
		self.assertEqual(parse_horario("13-17"), ("13:00:00", "17:00:00"))
		self.assertEqual(parse_horario("DESDE 20.00"), ("20:00:00", "22:00:00"))

	def test_map_espacio_aliases(self) -> None:
		self.assertEqual(map_espacio("P.B. SALON"), "SALON P.B.")
		self.assertEqual(map_espacio("GIM FISICO"), "GIMNASIO BAJO TRIBUNA")
		self.assertEqual(map_espacio("GIMNASIO 2"), CANCHA_2)
		self.assertEqual(map_espacio("GIMNASIO 1"), CANCHA_1)

	def test_build_titulo_con_etiqueta(self) -> None:
		titulo = build_horario_titulo(
			None,
			None,
			None,
			tipo_sesion="Entrenamiento",
			etiqueta='U11 Y U13 "AMARILLO" — SANTIAGO',
		)
		self.assertIn("U11", titulo)
		self.assertIn("Entrenamiento", titulo)

	def test_fixture_csv_carga_filas(self) -> None:
		path = default_horarios_csv_path()
		self.assertTrue(path.exists(), msg=str(path))
		rows = load_csv_rows(path)
		parsed = [r for r in rows if not isinstance(r, str)]
		self.assertGreaterEqual(len(parsed), 150)

	def test_match_actividad_basquet_femenino_y_patin(self) -> None:
		self.assertEqual(match_actividad("BASQUET FEMENINO U9 U11"), "Basquet Femenino")
		self.assertEqual(match_actividad("ESCUELITA U12"), "Basquet Escuelita")
		self.assertEqual(match_actividad("PATIN ARTISTICO"), "Patin Artistico")


class TestImportHorariosIntegration(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_import_a_espacio_de_prueba(self) -> None:
		path = default_horarios_csv_path()
		result = import_horarios_csv(path, replace_weekdays=True)
		self.assertGreater(result["horarios_creados"], 100)
		self.assertIn(CANCHA_1, result["espacios_actualizados"])
		cancha1 = frappe.get_doc("Espacio", CANCHA_1)
		lunes = [h for h in cancha1.horarios if h.dia_semana == "Lunes"]
		self.assertGreater(len(lunes), 5)
		self.assertFalse(frappe.db.exists("Espacio", "GIMNASIO 1"))

	def test_import_sabado_cancha_1_y_2(self) -> None:
		path = default_horarios_sabado_csv_path()
		self.assertTrue(path.exists())
		# Preservar L–V: importar sábado no debe vaciar lunes
		import_horarios_csv(default_horarios_csv_path(), replace_weekdays=True)
		result = import_horarios_sabado(path)
		self.assertEqual(result["horarios_creados"], 5)
		self.assertIn(CANCHA_1, result["espacios_actualizados"])
		self.assertIn(CANCHA_2, result["espacios_actualizados"])

		cancha1 = frappe.get_doc("Espacio", CANCHA_1)
		sab = [h for h in cancha1.horarios if h.dia_semana == "Sabado"]
		self.assertEqual(len(sab), 4)
		lunes = [h for h in cancha1.horarios if h.dia_semana == "Lunes"]
		self.assertGreater(len(lunes), 0)

		cancha2 = frappe.get_doc("Espacio", CANCHA_2)
		sab2 = [h for h in cancha2.horarios if h.dia_semana == "Sabado"]
		self.assertEqual(len(sab2), 1)
		self.assertEqual(str(sab2[0].hora_desde)[:5], "14:00")
		self.assertEqual(str(sab2[0].hora_hasta)[:5], "17:00")
		self.assertEqual(sab2[0].actividad, "Patin Artistico")
