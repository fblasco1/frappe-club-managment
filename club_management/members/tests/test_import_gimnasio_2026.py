"""Import del listado del gimnasio 2026 (spec import_gimnasio_2026.md)."""

from __future__ import annotations

import csv
import os
import tempfile

import frappe

from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO
from club_management.members.ops.import_gimnasio_2026 import (
	agrupar_no_socios,
	normalizar_nombre,
	run,
)
from club_management.members.services.cuotas_sociales_setup import sync_cuotas_sociales_club
from club_management.members.services.practicante_no_socio import (
	ACTIVIDAD_GIMNASIO,
	CONDICION_NO_SOCIO,
	CONDICION_SOCIO,
	grupo_gimnasio_por_condicion,
)
from club_management.members.services.socio_transitions import cambiar_estado
from club_management.members.test_helpers import MembersTestCase, insert_socio

HEADER = ["Nombre y Apellido", "Condición", "Profesor / Turno", "Tipo de Membresía"]


def _inscripcion_gym(socio: str) -> str | None:
	actividad = frappe.db.get_value("Actividad", {"titulo": ACTIVIDAD_GIMNASIO}, "name") or ACTIVIDAD_GIMNASIO
	return frappe.db.get_value(
		"Inscripcion Actividad",
		{"socio": socio, "actividad": actividad, "estado": "Activa"},
		"grupo_actividad",
	)


class TestNormalizacion(MembersTestCase):
	def test_normalizar_nombre(self) -> None:
		self.assertEqual(normalizar_nombre("  María  Mercedez Gómez "), "MARIA MERCEDEZ GOMEZ")
		self.assertEqual(normalizar_nombre("ORNELLA CAÑETE"), "ORNELLA CANETE")

	def test_agrupa_variantes_y_prioriza_mes(self) -> None:
		grupos = agrupar_no_socios(
			[
				("FLORENCIA MUSCALI", "HORA"),
				("FLORENCIA MUSCARI", "HORA"),
				("JULIETA ARECHAGA", "MES"),
				("Julieta Arechaga", "HORA"),
			]
		)
		self.assertEqual(len(grupos), 2)
		arechaga = next(g for g in grupos if "ARECHAGA" in g["nombre"])
		self.assertEqual(arechaga["membresia"], "MES")

	def test_separar_nombre(self) -> None:
		from club_management.members.ops.import_gimnasio_2026 import _Padron

		padron = _Padron()
		padron.freq_nombre.update({"GUSTAVO": 50, "DIEGO": 50, "CELESTE": 10})
		self.assertEqual(padron.separar_nombre("ALABARCEZ GUSTAVO"), ("Gustavo", "Alabarcez"))
		self.assertEqual(padron.separar_nombre("Celeste Del Cuelo"), ("Celeste", "Del Cuelo"))
		self.assertEqual(padron.separar_nombre("DIEGO MADEO"), ("Diego", "Madeo"))

	def test_no_agrupa_personas_distintas(self) -> None:
		grupos = agrupar_no_socios([("SOFIA CARUANA", "MES"), ("LAURA CARUANA", "MES")])
		self.assertEqual(len(grupos), 2)


class TestImportGimnasio2026(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		sync_cuotas_sociales_club()
		self.assertTrue(grupo_gimnasio_por_condicion(CONDICION_SOCIO))
		self.assertTrue(grupo_gimnasio_por_condicion(CONDICION_NO_SOCIO))

		self.socio_exacto = insert_socio(
			dni="79300001", email="gym.imp.exacto@example.com", nombre="Zulema", apellido="Testgimnasio"
		)
		cambiar_estado(self.socio_exacto.name, "Activo", motivo="Test import gym")
		self.socio_probable = insert_socio(
			dni="79300002", email="gym.imp.prob@example.com", nombre="Ramiro", apellido="Gimnasiopruebaa"
		)
		cambiar_estado(self.socio_probable.name, "Activo", motivo="Test import gym")
		self.adherente = insert_socio(
			dni="79300003",
			email="gym.imp.adh@example.com",
			nombre="Teodoro",
			apellido="Adherentegym",
			categoria="Adherente",
		)
		cambiar_estado(self.adherente.name, "Activo", motivo="Test import gym")

		fd, self.csv_path = tempfile.mkstemp(suffix=".csv")
		with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
			writer = csv.writer(fh)
			writer.writerow(HEADER)
			writer.writerows(
				[
					["ZULEMA TESTGIMNASIO", "Socio", "Zara", "MES"],
					["Zulema Testgimnasio", "Socio", "Ana", "MES"],
					["RAMIRO GIMNASIOPRUEBA", "Socio", "Zara", "MES"],
					["PERSONA INEXISTENTEGYM", "Socio", "Zara", "MES"],
					["ODILIA NUEVAGYM", "No socio", "Noelia", "MES"],
					["BRUNO HORAGYM", "No socio", "Noelia", "HORA"],
					["Bruno Horagymm", "No socio", "Ana", "HORA"],
					["TEODORO ADHERENTEGYM", "No socio", "Facundo", "MES"],
					["GONZALO", "No socio", "Facundo", "HORA"],
				]
			)

	def tearDown(self) -> None:
		os.unlink(self.csv_path)
		super().tearDown()

	def _apply(self, **kwargs) -> dict:
		return run(csv_path=self.csv_path, apply=True, confirm="local-dev", **kwargs)

	def test_dry_run_no_escribe(self) -> None:
		antes = frappe.db.count("Socio", {"categoria": CATEGORIA_NO_SOCIO})
		report = run(csv_path=self.csv_path)
		self.assertEqual(frappe.db.count("Socio", {"categoria": CATEGORIA_NO_SOCIO}), antes)
		self.assertIsNone(_inscripcion_gym(self.socio_exacto.name))
		self.assertTrue(report["dry_run"])

	def test_apply_bloqueado_sin_confirm(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			run(csv_path=self.csv_path, apply=True)

	def test_apply_completo(self) -> None:
		report = self._apply()
		grupo_socio = grupo_gimnasio_por_condicion(CONDICION_SOCIO)
		grupo_ns = grupo_gimnasio_por_condicion(CONDICION_NO_SOCIO)

		self.assertEqual(_inscripcion_gym(self.socio_exacto.name), grupo_socio)
		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": self.socio_exacto.name, "estado": "Activa"}), 1
		)
		self.assertIsNone(_inscripcion_gym(self.socio_probable.name))
		self.assertEqual(_inscripcion_gym(self.adherente.name), grupo_socio)

		probables = {p["csv"]: p for p in report["probables"]}
		self.assertIn("RAMIRO GIMNASIOPRUEBA", probables)
		self.assertIn(self.socio_probable.name, [c["socio"] for c in probables["RAMIRO GIMNASIOPRUEBA"]["candidatos"]])
		self.assertIn("PERSONA INEXISTENTEGYM", [r["csv"] for r in report["no_encontrados"]])
		self.assertIn("GONZALO", [r["csv"] for r in report["nombre_incompleto"]])

		odilia = frappe.db.get_value(
			"Socio", {"categoria": CATEGORIA_NO_SOCIO, "apellido": "Nuevagym"}, ["name", "dni"], as_dict=True
		)
		self.assertTrue(odilia.name.startswith("NS-"))
		self.assertTrue(odilia.dni.startswith("GYM-PEND-"))
		self.assertEqual(_inscripcion_gym(odilia.name), grupo_ns)

		brunos = frappe.get_all(
			"Socio", filters={"categoria": CATEGORIA_NO_SOCIO, "apellido": ["like", "Horagym%"]}, pluck="name"
		)
		self.assertEqual(len(brunos), 1)
		self.assertIsNone(_inscripcion_gym(brunos[0]))
		self.assertFalse(frappe.db.exists("Socio", {"categoria": CATEGORIA_NO_SOCIO, "apellido": "Adherentegym"}))

		lineas = {l["linea"]: l for l in report["lineas"]}
		self.assertEqual(len(lineas), 9)
		self.assertEqual(lineas[2]["situacion"], "Inscripto en Gimnasio / Socio")
		self.assertIn("Misma persona que la línea 2", lineas[3]["detalle"])
		self.assertEqual(lineas[4]["situacion"], "Pendiente: coincidencia dudosa")
		self.assertEqual(lineas[5]["situacion"], "Pendiente: socio no encontrado")
		self.assertEqual(lineas[6]["socio"], odilia.name)
		self.assertEqual(lineas[6]["dni"], odilia.dni)
		self.assertTrue(lineas[6]["pendiente"])
		self.assertIn("Entrenamiento por hora", lineas[7]["situacion"])
		self.assertIn("Misma persona que la línea 7", lineas[8]["detalle"])
		self.assertIn("figuraba como No socio", lineas[9]["detalle"])
		self.assertEqual(lineas[10]["situacion"], "Pendiente: nombre incompleto")
		self.assertNotIn("Sin procesar", {l["situacion"] for l in report["lineas"]})

		antes = frappe.db.count("Socio", {"categoria": CATEGORIA_NO_SOCIO})
		self._apply()
		self.assertEqual(frappe.db.count("Socio", {"categoria": CATEGORIA_NO_SOCIO}), antes)
		self.assertEqual(
			frappe.db.count("Inscripcion Actividad", {"socio": odilia.name, "estado": "Activa"}), 1
		)

	def test_confirmados_inscribe_probable(self) -> None:
		self._apply(confirmados={"RAMIRO GIMNASIOPRUEBA": self.socio_probable.name})
		self.assertEqual(_inscripcion_gym(self.socio_probable.name), grupo_gimnasio_por_condicion(CONDICION_SOCIO))
