"""Tests migración inscripciones básquet legacy → Basquet unificado."""

from __future__ import annotations

import frappe

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.activities.services.migrate_basquet_inscripciones import (
	migrate_basquet_inscripciones_activas,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestMigrateBasquetInscripciones(MembersTestCase):
	def _ensure_legacy_basquet_masculino_u13(self) -> tuple[str, str, str]:
		if not frappe.db.exists("Actividad", "Basquet Masculino"):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": "Basquet Masculino",
					"titulo": "Basquet Masculino",
					"usa_grupos": 1,
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		grupo = "Basquet Masculino / Tira Azul"
		if not frappe.db.exists("Grupo Actividad", grupo):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": grupo,
					"actividad": "Basquet Masculino",
					"titulo": "Tira Azul",
					"habilitada": 1,
					"orden": 10,
				}
			).insert(ignore_permissions=True)
		equipo = f"{grupo} / U13"
		if not frappe.db.exists("Equipo Actividad", equipo):
			frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": equipo,
					"grupo_actividad": grupo,
					"titulo": "U13",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		return "Basquet Masculino", grupo, equipo

	def test_migra_inscripcion_masculino_azul_u13(self) -> None:
		socio = insert_socio(dni="71002001", email="mig.basq@example.com", estado="Activo")
		actividad, grupo, equipo = self._ensure_legacy_basquet_masculino_u13()
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": actividad, "grupo": grupo, "equipo": equipo}],
			activar=False,
		)
		seed_estructura_actividades_completa(crear_equipos=True)
		migrate_basquet_inscripciones_activas()

		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		self.assertTrue(basquet)
		ins = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "estado": "Activa"},
			["actividad", "grupo_actividad", "equipo_actividad"],
			as_dict=True,
		)
		self.assertEqual(ins.actividad, basquet)
		self.assertEqual(ins.grupo_actividad, f"{basquet} / Masculino / Azul")
		self.assertEqual(ins.equipo_actividad, f"{basquet} / Masculino / Azul / U13")
		self.assertIn("Basquet", frappe.db.get_value("Socio", socio.name, "actividad") or "")
		self.assertNotIn("Basquet Masculino", frappe.db.get_value("Socio", socio.name, "actividad") or "")

	def test_migra_femenino_superior_fem(self) -> None:
		if not frappe.db.exists("Actividad", "Basquet Femenino"):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": "Basquet Femenino",
					"titulo": "Basquet Femenino",
					"usa_grupos": 1,
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		grupo = "Basquet Femenino / Femenino"
		if not frappe.db.exists("Grupo Actividad", grupo):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": grupo,
					"actividad": "Basquet Femenino",
					"titulo": "Femenino",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		equipo = f"{grupo} / Superior Fem"
		if not frappe.db.exists("Equipo Actividad", equipo):
			frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": equipo,
					"grupo_actividad": grupo,
					"titulo": "Superior Fem",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)

		socio = insert_socio(dni="71002002", email="mig.basq.fem@example.com", estado="Activo")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": "Basquet Femenino", "grupo": grupo, "equipo": equipo}],
			activar=False,
		)
		seed_estructura_actividades_completa(crear_equipos=True)
		migrate_basquet_inscripciones_activas()

		basquet = frappe.db.get_value("Actividad", {"titulo": "Basquet"}, "name")
		ins = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "estado": "Activa"},
			["grupo_actividad", "equipo_actividad"],
			as_dict=True,
		)
		self.assertEqual(ins.grupo_actividad, f"{basquet} / Femenino / Superior")
		self.assertEqual(ins.equipo_actividad, f"{basquet} / Femenino / Superior / Superior Fem")
