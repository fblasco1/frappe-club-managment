"""Tests del DocType Equipo Actividad."""

from __future__ import annotations

import frappe

from club_management.activities.services.inscripcion_actividad_roster import (
	list_socios_inscripcion_grupo_equipo,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestEquipoActividad(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		self._secretaria = "secretaria_equipo_roster@example.com"
		if not frappe.db.exists("User", self._secretaria):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": self._secretaria,
					"first_name": "Secretaria",
					"send_welcome_email": 0,
					"roles": [{"role": "Secretaria"}],
				}
			).insert(ignore_permissions=True)

	def _ensure_estructura_basquet(self) -> tuple[str, str, str]:
		actividad = "Basquet Equipo Roster Test"
		grupo = f"{actividad} / Tira Roster"
		equipo_a = f"{grupo} / U13 Roster"
		equipo_b = f"{grupo} / U15 Roster"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": actividad,
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Grupo Actividad", grupo):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": grupo,
					"actividad": actividad,
					"titulo": "Tira Roster",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		for equipo_name, titulo in ((equipo_a, "U13 Roster"), (equipo_b, "U15 Roster")):
			if not frappe.db.exists("Equipo Actividad", equipo_name):
				frappe.get_doc(
					{
						"doctype": "Equipo Actividad",
						"name": equipo_name,
						"grupo_actividad": grupo,
						"titulo": titulo,
						"habilitada": 1,
					}
				).insert(ignore_permissions=True)
		return actividad, grupo, equipo_a

	def _inscribir(
		self,
		socio_name: str,
		actividad: str,
		*,
		grupo: str | None = None,
		equipo: str | None = None,
	) -> None:
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio_name,
				"actividad": actividad,
				"grupo_actividad": grupo,
				"equipo_actividad": equipo,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

	def test_list_socios_por_equipo(self) -> None:
		actividad, grupo, equipo_a = self._ensure_estructura_basquet()
		equipo_b = f"{grupo} / U15 Roster"
		socio_a = insert_socio(dni="70993010", email="equipo.roster.a@example.com", estado="Activo")
		socio_b = insert_socio(dni="70993011", email="equipo.roster.b@example.com", estado="Activo")
		self._inscribir(socio_a.name, actividad, grupo=grupo, equipo=equipo_a)
		self._inscribir(socio_b.name, actividad, grupo=grupo, equipo=equipo_b)

		rows = list_socios_inscripcion_grupo_equipo(
			grupo_actividad=grupo,
			equipo_actividad=equipo_a,
		)
		self.assertEqual([row["socio"] for row in rows], [socio_a.name])
		self.assertEqual(rows[0]["nombre"], socio_a.nombre)
		self.assertEqual(rows[0]["apellido"], socio_a.apellido)
		self.assertEqual(rows[0]["dni"], socio_a.dni)
		self.assertEqual(rows[0]["telefono_movil"], socio_a.telefono_movil)

	def test_list_socios_por_grupo_sin_equipo(self) -> None:
		actividad, grupo, equipo_a = self._ensure_estructura_basquet()
		socio_grupo = insert_socio(dni="70993012", email="equipo.roster.grupo@example.com", estado="Activo")
		socio_equipo = insert_socio(dni="70993013", email="equipo.roster.equipo@example.com", estado="Activo")
		self._inscribir(socio_grupo.name, actividad, grupo=grupo)
		self._inscribir(socio_equipo.name, actividad, grupo=grupo, equipo=equipo_a)

		rows = list_socios_inscripcion_grupo_equipo(grupo_actividad=grupo)
		self.assertEqual({row["socio"] for row in rows}, {socio_grupo.name, socio_equipo.name})

	def test_list_socios_vacio_sin_grupo_ni_equipo(self) -> None:
		self.assertEqual(list_socios_inscripcion_grupo_equipo(), [])

	def test_api_roster_requiere_secretaria(self) -> None:
		from club_management.activities.api.equipo_actividad_desk import list_socios_grupo_equipo

		actividad, grupo, equipo = self._ensure_estructura_basquet()
		socio = insert_socio(dni="70993014", email="equipo.roster.perm@example.com", estado="Activo")
		self._inscribir(socio.name, actividad, grupo=grupo, equipo=equipo)

		email = f"socio_{socio.dni}@example.com"
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Socio",
					"send_welcome_email": 0,
					"roles": [{"role": "Socio"}],
				}
			).insert(ignore_permissions=True)

		frappe.set_user(email)
		try:
			with self.assertRaises(frappe.PermissionError):
				list_socios_grupo_equipo(equipo_actividad=equipo)
		finally:
			frappe.set_user("Administrator")

		frappe.set_user(self._secretaria)
		try:
			rows = list_socios_grupo_equipo(equipo_actividad=equipo)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["socio"], socio.name)

	def test_api_arancel_resumen_efectivo(self) -> None:
		from club_management.activities.api.equipo_actividad_desk import get_arancel_resumen
		from club_management.activities.services.gestion_actividades_panel import set_arancel

		actividad, grupo, equipo = self._ensure_estructura_basquet()
		item_group = frappe.db.get_value("Item Group", {}, "name") or "All Item Groups"
		item_code = "TEST-EQ-RESUMEN-AR"
		if not frappe.db.exists("Item", item_code):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": "Arancel resumen test",
					"item_group": item_group,
					"is_stock_item": 0,
					"standard_rate": 3200,
				}
			).insert(ignore_permissions=True)
		else:
			frappe.db.set_value("Item", item_code, "standard_rate", 3200)
		set_arancel(doctype="Grupo Actividad", name=grupo, item=item_code, rate=3200)

		frappe.set_user(self._secretaria)
		try:
			resumen = get_arancel_resumen(equipo)
		finally:
			frappe.set_user("Administrator")

		self.assertEqual(resumen["item"], item_code)
		self.assertEqual(resumen["origen"], "Grupo")
		self.assertEqual(resumen["rate"], 3200.0)
		self.assertTrue(resumen.get("item_name"))
