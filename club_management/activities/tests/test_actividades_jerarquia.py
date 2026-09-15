"""Tests jerarquía Actividad → Grupo → Equipo."""

from __future__ import annotations

import frappe

from club_management.activities.services.inscripcion_socio import (
	actividades_resumen_socio,
	inscribir_socio_selecciones,
	resolve_item_arancel_inscripcion,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestActividadesJerarquia(MembersTestCase):
	def _ensure_basquet_con_grupos(self) -> tuple[str, str, str]:
		from club_management.activities.services.actividades_icdpe_catalog import (
			_resolve_actividad_docname,
		)

		actividad_name = _resolve_actividad_docname("Basquet Masculino")
		if not actividad_name:
			frappe.get_doc(
				{
					"doctype": "Actividad",
					"name": "Basquet Masculino",
					"titulo": "Basquet Masculino",
					"usa_grupos": 1,
					"habilitada": 1,
				}
			).insert(ignore_permissions=True)
			actividad_name = "Basquet Masculino"
		else:
			frappe.db.set_value("Actividad", actividad_name, {"usa_grupos": 1, "titulo": "Basquet Masculino"})

		grupo_name = frappe.db.get_value(
			"Grupo Actividad",
			{"actividad": actividad_name, "titulo": "Tira Azul"},
			"name",
		)
		if not grupo_name:
			grupo_doc = frappe.get_doc(
				{
					"doctype": "Grupo Actividad",
					"name": f"{actividad_name} / Tira Azul",
					"actividad": actividad_name,
					"titulo": "Tira Azul",
					"habilitada": 1,
					"orden": 10,
				}
			)
			grupo_doc.insert(ignore_permissions=True)
			grupo_name = grupo_doc.name

		equipo_name = frappe.db.get_value(
			"Equipo Actividad",
			{"grupo_actividad": grupo_name, "titulo": "Categoria U11"},
			"name",
		)
		if not equipo_name:
			equipo_doc = frappe.get_doc(
				{
					"doctype": "Equipo Actividad",
					"name": f"{grupo_name} / Categoria U11",
					"grupo_actividad": grupo_name,
					"titulo": "Categoria U11",
					"habilitada": 1,
				}
			)
			equipo_doc.insert(ignore_permissions=True)
			equipo_name = equipo_doc.name

		return actividad_name, grupo_name, equipo_name

	def test_inscripcion_con_grupo_y_equipo(self) -> None:
		socio = insert_socio(dni="71001001", email="jerarq@example.com", estado="Activo")
		actividad, grupo, equipo = self._ensure_basquet_con_grupos()

		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": actividad, "grupo": grupo, "equipo": equipo}],
			activar=False,
		)

		ins = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "estado": "Activa"},
			["actividad", "grupo_actividad", "equipo_actividad"],
			as_dict=True,
		)
		self.assertEqual(
			frappe.db.get_value("Actividad", ins.actividad, "titulo"),
			"Basquet Masculino",
		)
		self.assertEqual(ins.grupo_actividad, grupo)
		self.assertEqual(ins.equipo_actividad, equipo)
		self.assertIn("Tira Azul", actividades_resumen_socio(socio.name))
		self.assertIn("Categoria U11", actividades_resumen_socio(socio.name))

	def test_zumba_sin_grupo(self) -> None:
		if not frappe.db.exists("Actividad", "Zumba"):
			frappe.get_doc(
				{"doctype": "Actividad", "titulo": "Zumba", "usa_grupos": 0, "habilitada": 1}
			).insert(ignore_permissions=True)
		socio = insert_socio(dni="71001002", email="zumba@example.com", estado="Activo")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": "Zumba"}],
			activar=False,
		)
		self.assertEqual(actividades_resumen_socio(socio.name), "Zumba")

	def test_item_arancel_desde_grupo(self) -> None:
		_, grupo, _ = self._ensure_basquet_con_grupos()
		item_code = "ICDPE-ARANCEL-MENSUAL-basquet-tira-azul"
		if not frappe.db.exists("Item", item_code):
			if not frappe.db.exists("UOM", "Nos"):
				frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert(ignore_permissions=True)
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": item_code,
					"item_name": "Arancel Tira Azul",
					"item_group": "All Item Groups",
					"stock_uom": "Nos",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)
		frappe.db.set_value("Grupo Actividad", grupo, "item", item_code)

		socio = insert_socio(dni="71001003", email="item.gr@example.com", estado="Activo")
		inscribir_socio_selecciones(
			socio.name,
			[{"actividad": "Basquet Masculino", "grupo": grupo}],
			activar=False,
		)
		ins_name = frappe.db.get_value(
			"Inscripcion Actividad",
			{"socio": socio.name, "grupo_actividad": grupo},
			"name",
		)
		self.assertEqual(resolve_item_arancel_inscripcion(ins_name), item_code)
