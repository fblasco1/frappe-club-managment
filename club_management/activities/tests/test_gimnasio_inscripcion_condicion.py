"""Inscripción al gimnasio según condición socio / no socio (spec gimnasio_cobro_socios_no_socios.md)."""

from __future__ import annotations

import frappe

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.members.doctype.socio.socio import CATEGORIA_NO_SOCIO
from club_management.members.test_helpers import MembersTestCase, insert_socio

ACTIVIDAD_GYM = "Gimnasio Fitness"
GRUPO_GYM_NO_SOCIO = f"{ACTIVIDAD_GYM} / No Socio"
GRUPO_GYM_SOCIO = f"{ACTIVIDAD_GYM} / Socio"


class TestGimnasioInscripcionCondicion(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		seed_estructura_actividades_completa(crear_equipos=False)

	def _inscribir(self, socio: str, actividad: str, grupo: str | None):
		return frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio,
				"actividad": actividad,
				"grupo_actividad": grupo,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

	def test_seed_marca_condicion_y_admite_no_socios(self) -> None:
		self.assertEqual(
			frappe.db.get_value("Grupo Actividad", GRUPO_GYM_NO_SOCIO, "condicion_socio"), "No Socio"
		)
		self.assertEqual(frappe.db.get_value("Grupo Actividad", GRUPO_GYM_SOCIO, "condicion_socio"), "Socio")
		self.assertEqual(int(frappe.db.get_value("Actividad", ACTIVIDAD_GYM, "admite_no_socios") or 0), 1)

	def test_no_socio_en_grupo_no_socio_ok(self) -> None:
		ns = insert_socio(dni="77001001", email="gym.ns.ok@example.com", categoria=CATEGORIA_NO_SOCIO)
		ins = self._inscribir(ns.name, ACTIVIDAD_GYM, GRUPO_GYM_NO_SOCIO)
		self.assertTrue(ins.name)

	def test_no_socio_en_grupo_socio_rechazado(self) -> None:
		ns = insert_socio(dni="77001002", email="gym.ns.rech@example.com", categoria=CATEGORIA_NO_SOCIO)
		with self.assertRaises(frappe.ValidationError):
			self._inscribir(ns.name, ACTIVIDAD_GYM, GRUPO_GYM_SOCIO)

	def test_socio_en_grupo_no_socio_rechazado(self) -> None:
		socio = insert_socio(dni="77001003", email="gym.soc.rech@example.com")
		with self.assertRaises(frappe.ValidationError):
			self._inscribir(socio.name, ACTIVIDAD_GYM, GRUPO_GYM_NO_SOCIO)

	def test_socio_en_grupo_socio_ok(self) -> None:
		socio = insert_socio(dni="77001004", email="gym.soc.ok@example.com")
		ins = self._inscribir(socio.name, ACTIVIDAD_GYM, GRUPO_GYM_SOCIO)
		self.assertTrue(ins.name)

	def test_no_socio_en_actividad_sin_admite_no_socios_rechazado(self) -> None:
		otra = frappe.db.get_value(
			"Actividad",
			{"habilitada": 1, "name": ["!=", ACTIVIDAD_GYM], "admite_no_socios": 0},
			["name", "usa_grupos"],
			as_dict=True,
		)
		if not otra:
			self.skipTest("No hay otra actividad habilitada")
		grupo = None
		if otra.usa_grupos:
			grupo = frappe.db.get_value("Grupo Actividad", {"actividad": otra.name, "habilitada": 1}, "name")
		ns = insert_socio(dni="77001005", email="gym.ns.otra@example.com", categoria=CATEGORIA_NO_SOCIO)
		with self.assertRaises(frappe.ValidationError):
			self._inscribir(ns.name, otra.name, grupo)
