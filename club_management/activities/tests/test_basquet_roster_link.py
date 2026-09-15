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

	def test_map_u21_femenino_superior(self) -> None:
		sel = map_basquet_seleccion("U21", "Femenino")
		self.assertEqual(sel["grupo"], "Femenino / Superior")
		self.assertEqual(sel["equipo"], "Superior Fem")

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


class TestImportRosterJugadores(MembersTestCase):
	def test_find_socio_por_nombre_completo(self) -> None:
		from club_management.activities.services.basquet_roster_link import (
			_find_socio_by_nombre,
			normalize_roster_nombre,
		)

		socio = insert_socio(
			dni="88100001",
			apellido="ZZTESTROSTER",
			nombre="Nombre Busqueda",
			email="roster.nombre@example.com",
			estado="Activo",
		)
		self.assertEqual(
			frappe.db.get_value("Socio", socio.name, "nombre_completo"),
			"ZZTESTROSTER, Nombre Busqueda",
		)
		self.assertEqual(normalize_roster_nombre("ZZTESTROSTER, Nombre Busqueda "), "ZZTESTROSTER, NOMBRE BUSQUEDA")
		self.assertEqual(_find_socio_by_nombre("ZZTESTROSTER, Nombre Busqueda"), socio.name)

	def test_import_clasifica_logs(self) -> None:
		import csv
		import tempfile
		from pathlib import Path

		from club_management.activities.services.basquet_roster_link import import_roster_jugadores

		seed_estructura_actividades_completa(crear_equipos=True)
		con_dni = insert_socio(
			dni="88100002",
			apellido="ZZTESTROSTER",
			nombre="Con Dni",
			email="roster.csv1@example.com",
			estado="Activo",
		)
		por_nombre = insert_socio(
			dni="88100003",
			apellido="ZZTESTROSTER",
			nombre="Por Nombre",
			email="roster.csv2@example.com",
			estado="Activo",
		)
		ya_inscripto = insert_socio(
			dni="88100004",
			apellido="ZZTESTROSTER",
			nombre="Ya Inscripto",
			email="roster.csv3@example.com",
			estado="Activo",
		)
		inscribir_socio_selecciones(
			ya_inscripto.name,
			[{"actividad": "Basquet", "grupo": "Mixto / Escuela", "equipo": "U7 / U9"}],
			activar=False,
		)

		with tempfile.TemporaryDirectory() as tmp:
			csv_path = Path(tmp) / "jugadores.csv"
			with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
				writer = csv.DictWriter(
					handle,
					fieldnames=[
						"Numero",
						"DNI",
						"Nombre y Apellido",
						"Equipo 2026",
						"Categoria 2026",
					],
				)
				writer.writeheader()
				writer.writerow(
					{
						"Numero": "1",
						"DNI": "",
						"Nombre y Apellido": "ZZTESTROSTER, Sin Dni",
						"Equipo 2026": "Escuelita",
						"Categoria 2026": "U7",
					}
				)
				writer.writerow(
					{
						"Numero": "2",
						"DNI": "99999999",
						"Nombre y Apellido": "ZZTESTROSTER, Fantasma",
						"Equipo 2026": "Escuelita",
						"Categoria 2026": "U7",
					}
				)
				writer.writerow(
					{
						"Numero": "3",
						"DNI": "",
						"Nombre y Apellido": "ZZTESTROSTER, Por Nombre",
						"Equipo 2026": "Escuelita",
						"Categoria 2026": "U7",
					}
				)
				writer.writerow(
					{
						"Numero": "4",
						"DNI": "88100002",
						"Nombre y Apellido": "ZZTESTROSTER, Con Dni",
						"Equipo 2026": "Escuelita",
						"Categoria 2026": "U7",
					}
				)
				writer.writerow(
					{
						"Numero": "5",
						"DNI": "88100004",
						"Nombre y Apellido": "ZZTESTROSTER, Ya Inscripto",
						"Equipo 2026": "Escuelita",
						"Categoria 2026": "U7",
					}
				)

			stats = import_roster_jugadores(
				source_path=str(csv_path),
				dry_run=True,
				output_dir=tmp,
			)

			self.assertEqual(stats["no_padron_sin_dni"], 1)
			self.assertEqual(stats["no_padron_con_dni"], 1)
			self.assertEqual(stats["ya_inscriptos"], 1)
			self.assertEqual(stats["inscripciones_nuevas"], 2)
			self.assertTrue(Path(stats["log_paths"]["no_padron_sin_dni"]).is_file())
			self.assertTrue(Path(stats["log_paths"]["reporte_html"]).is_file())
			html = Path(stats["log_paths"]["reporte_html"]).read_text(encoding="utf-8")
			self.assertIn("Qué ajustar para completar el import", html)
			self.assertIn("No están en el padrón y sin DNI", html)
			self.assertIn("informe-import-cobranza-basquet", html)
			self.assertIn("informeToggleAll", html)
			self.assertNotIn("Cobranza y cargos", html)
