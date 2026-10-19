"""Tests reporte Inscriptos por Actividad (spec reporte_inscriptos_actividad.md)."""

from __future__ import annotations

import frappe

from club_management.activities.services.reporte_inscriptos_actividad import (
	get_inscriptos_por_actividad_data,
	get_report_columns,
)
from club_management.members.doctype.socio.socio import format_socio_nombre_completo
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestReporteInscriptosActividad(MembersTestCase):
	def _ensure_jerarquia(self) -> tuple[str, str, str]:
		actividad = "Futbol KPI Report"
		grupo_name = f"{actividad} / TABI A"
		equipo_name = f"{grupo_name} / 1ra"
		if not frappe.db.exists("Actividad", actividad):
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"titulo": actividad,
					"habilitada": 1,
					"usa_grupos": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Grupo Actividad", grupo_name):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": grupo_name,
					"actividad": actividad,
					"titulo": "TABI A",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Equipo Actividad", equipo_name):
			frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": equipo_name,
					"grupo_actividad": grupo_name,
					"titulo": "1ra",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		return actividad, grupo_name, equipo_name

	def test_columnas_visuales_sin_actividad_ni_grupo(self) -> None:
		fieldnames = [c["fieldname"] for c in get_report_columns()]
		self.assertEqual(fieldnames, ["nro_socio", "nombre", "equipo_categoria", "estado"])
		self.assertNotIn("actividad", fieldnames)
		self.assertNotIn("grupo_actividad", fieldnames)

	def test_filas_incluyen_nombre_y_equipo(self) -> None:
		actividad, grupo, equipo = self._ensure_jerarquia()
		socio = insert_socio(
			dni="73103001",
			email="inscriptos.rep@example.com",
			nombre="Ana",
			apellido="Gómez",
			estado="Activo",
		)
		frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": actividad,
				"grupo_actividad": grupo,
				"equipo_actividad": equipo,
				"estado": "Activa",
			}
		).insert(ignore_permissions=True)

		rows = get_inscriptos_por_actividad_data({"actividad": actividad, "estado": "Activa"})
		mine = [r for r in rows if r["nro_socio"] == socio.name]
		self.assertEqual(len(mine), 1)
		self.assertEqual(mine[0]["nombre"], format_socio_nombre_completo("Gómez", "Ana"))
		self.assertEqual(mine[0]["equipo_categoria"], equipo)
		self.assertEqual(mine[0]["estado"], "Activa")

	def test_lista_meta_nombre_visible_filtros_sin_redundancia(self) -> None:
		meta = frappe.get_meta("Inscripcion Actividad")
		socio_nombre = meta.get_field("socio_nombre")
		self.assertIsNotNone(socio_nombre)
		self.assertEqual(socio_nombre.in_list_view, 1)
		self.assertEqual(meta.get_field("actividad").in_list_view, 0)
		self.assertEqual(meta.get_field("actividad").in_standard_filter, 1)
		self.assertEqual(meta.get_field("grupo_actividad").in_list_view, 0)
		self.assertEqual(meta.get_field("grupo_actividad").in_standard_filter, 1)
		self.assertEqual(meta.get_field("equipo_actividad").in_list_view, 1)

	def test_socio_nombre_se_sincroniza_al_guardar(self) -> None:
		actividad, grupo, equipo = self._ensure_jerarquia()
		socio = insert_socio(
			dni="73103002",
			email="inscriptos.nombre@example.com",
			nombre="Luis",
			apellido="Pérez",
			estado="Activo",
		)
		doc = frappe.get_doc(
			{
				"doctype": "Inscripcion Actividad",
				"socio": socio.name,
				"actividad": actividad,
				"grupo_actividad": grupo,
				"equipo_actividad": equipo,
				"estado": "Activa",
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.socio_nombre, format_socio_nombre_completo("Pérez", "Luis"))

	def test_sidebar_incluye_reporte(self) -> None:
		from pathlib import Path

		from club_management.activities.setup.actividades_workspace_sidebar import SIDEBAR_ITEMS

		links = [i.get("link_to") for i in SIDEBAR_ITEMS if i.get("link_type") == "Report"]
		self.assertIn("Inscriptos por Actividad", links)
		boot_js = (
			Path(__file__).resolve().parents[2] / "public" / "js" / "actividades_sidebar_boot.js"
		).read_text(encoding="utf-8")
		self.assertIn("Inscriptos por Actividad", boot_js)
		self.assertIn('ref_doctype: "Inscripcion Actividad"', boot_js)

	def test_equipo_query_acota_por_actividad(self) -> None:
		from club_management.activities.services.reporte_inscriptos_actividad import (
			equipo_actividad_query,
		)

		actividad, grupo, equipo = self._ensure_jerarquia()
		otra = "Otra Actividad KPI Report"
		otro_grupo = f"{otra} / Extra"
		otro_equipo = f"{otro_grupo} / X"
		if not frappe.db.exists("Actividad", otra):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": otra, "habilitada": 1, "usa_grupos": 1}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Grupo Actividad", otro_grupo):
			frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": otro_grupo,
					"actividad": otra,
					"titulo": "Extra",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Equipo Actividad", otro_equipo):
			frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": otro_equipo,
					"grupo_actividad": otro_grupo,
					"titulo": "X",
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)

		rows = equipo_actividad_query(
			"Equipo Actividad",
			"",
			"name",
			0,
			50,
			{"actividad": actividad},
		)
		names = [r[0] for r in rows]
		self.assertIn(equipo, names)
		self.assertNotIn(otro_equipo, names)

		rows_grupo = equipo_actividad_query(
			"Equipo Actividad",
			"",
			"name",
			0,
			50,
			{"actividad": actividad, "grupo_actividad": grupo},
		)
		self.assertEqual([r[0] for r in rows_grupo], [equipo])
