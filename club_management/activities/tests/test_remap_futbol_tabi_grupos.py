"""Tests remap TABI Fútbol (spec remap_futbol_tabi_grupos.md)."""

from __future__ import annotations

import frappe

from club_management.activities.ops.remap_futbol_tabi_grupos import run
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestRemapFutbolTabiGrupos(MembersTestCase):
	def _ensure_grupos(self) -> None:
		if not frappe.db.exists("Actividad", "Futbol"):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": "Futbol", "habilitada": 1, "usa_grupos": 1}
			).insert(ignore_permissions=True)
		for name, titulo, hab in (
			("Futbol / TABI A", "TABI A", 1),
			("Futbol / TABI B", "TABI B", 1),
			("Futbol / TABI-1", "TABI-1", 0),
			("Futbol / TABI-2", "TABI-2", 0),
			("Futbol / Escuelita", "Escuelita", 0),
		):
			if frappe.db.exists("Grupo Actividad", name):
				continue
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": name,
					"actividad": "Futbol",
					"titulo": titulo,
					"habilitada": hab,
				}
			).insert(ignore_permissions=True)

	def _inscribir(self, *, dni: str, email: str, grupo: str, estado: str = "Activa") -> str:
		socio = insert_socio(dni=dni, email=email, estado="Activo")
		doc = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": "Futbol",
				"grupo_actividad": grupo,
				"estado": estado,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_dry_run_lista_sin_modificar(self) -> None:
		self._ensure_grupos()
		name = self._inscribir(dni="73104001", email="tabi1@example.com", grupo="Futbol / TABI-1")
		report = run(apply=False)
		self.assertTrue(any(r["inscripcion"] == name for r in report["a_remapear"]))
		self.assertEqual(
			frappe.db.get_value("Inscripcion Actividad", name, "grupo_actividad"),
			"Futbol / TABI-1",
		)

	def test_apply_remapea_tabi1_a_tabi_a(self) -> None:
		self._ensure_grupos()
		name = self._inscribir(dni="73104002", email="tabi1b@example.com", grupo="Futbol / TABI-1")
		report = run(apply=True, confirm="local-dev")
		self.assertIn(name, report["remapeadas"])
		self.assertEqual(
			frappe.db.get_value("Inscripcion Actividad", name, "grupo_actividad"),
			"Futbol / TABI A",
		)

	def test_apply_escuelita_y_tabi2_a_tabi_b(self) -> None:
		self._ensure_grupos()
		e = self._inscribir(dni="73104003", email="esc@example.com", grupo="Futbol / Escuelita")
		t2 = self._inscribir(dni="73104004", email="t2@example.com", grupo="Futbol / TABI-2")
		report = run(apply=True, confirm="local-dev")
		self.assertIn(e, report["remapeadas"])
		self.assertIn(t2, report["remapeadas"])
		self.assertEqual(
			frappe.db.get_value("Inscripcion Actividad", e, "grupo_actividad"),
			"Futbol / TABI B",
		)
		self.assertEqual(
			frappe.db.get_value("Inscripcion Actividad", t2, "grupo_actividad"),
			"Futbol / TABI B",
		)

	def test_conflicto_activa_no_remapea(self) -> None:
		self._ensure_grupos()
		socio = insert_socio(dni="73104005", email="conf@example.com", estado="Activo")
		destino = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": "Futbol",
				"grupo_actividad": "Futbol / TABI A",
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)
		# Legacy Activa creada vía DB para simular dato histórico inconsistente.
		legacy = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": "Futbol",
				"grupo_actividad": "Futbol / Escuelita",
				"estado": "Baja",
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value(
			"Inscripcion Actividad",
			legacy.name,
			{"grupo_actividad": "Futbol / TABI-1", "estado": "Activa"},
			update_modified=False,
		)

		report = run(apply=True, confirm="local-dev")
		self.assertTrue(any(c["inscripcion"] == legacy.name for c in report["conflictos"]))
		self.assertEqual(
			frappe.db.get_value("Inscripcion Actividad", legacy.name, "grupo_actividad"),
			"Futbol / TABI-1",
		)
		self.assertEqual(destino.grupo_actividad, "Futbol / TABI A")
