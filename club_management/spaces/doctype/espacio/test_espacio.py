"""Tests DocType Espacio (spec spaces_catalogo_ocupacion.md)."""

from __future__ import annotations

import frappe

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.helpers import ensure_actividad_tree, insert_espacio


class TestEspacio(MembersTestCase):
	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def test_crear_espacio_alquilable(self) -> None:
		name = insert_espacio("Cancha 1 Spaces Test", tipo="Cancha", alquilable=1)
		doc = frappe.get_doc("Espacio", name)
		self.assertEqual(doc.alquilable, 1)
		self.assertEqual(doc.habilitado, 1)

	def test_espacio_no_alquilable_con_grilla(self) -> None:
		name = insert_espacio(
			"Gimnasio Spaces Test",
			tipo="Gimnasio",
			alquilable=0,
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "18:00:00",
					"hora_hasta": "19:00:00",
					"tipo_sesion": "Preparacion Fisica",
				}
			],
		)
		doc = frappe.get_doc("Espacio", name)
		self.assertEqual(doc.alquilable, 0)
		self.assertEqual(len(doc.horarios), 1)
		self.assertEqual(doc.horarios[0].tipo_sesion, "Preparacion Fisica")

	def test_grilla_sin_solape(self) -> None:
		name = insert_espacio(
			"Cancha Sin Solape Test",
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "18:00:00",
					"hora_hasta": "19:00:00",
				},
				{
					"dia_semana": "Lunes",
					"hora_desde": "19:00:00",
					"hora_hasta": "20:00:00",
				},
			],
		)
		self.assertTrue(frappe.db.exists("Espacio", name))

	def test_varios_equipos_pueden_solapar_en_cancha(self) -> None:
		act, grupo, equipo_a = ensure_actividad_tree(
			"Basquet Multi Spaces",
			"Basquet Multi Spaces / Azul",
			"Basquet Multi Spaces / Azul / U11",
		)
		_act, _grupo, equipo_b = ensure_actividad_tree(
			"Basquet Multi Spaces",
			"Basquet Multi Spaces / Azul",
			"Basquet Multi Spaces / Azul / U13",
		)
		name = insert_espacio(
			"Cancha Multi Equipo",
			horarios=[
				{
					"dia_semana": "Lunes",
					"hora_desde": "18:00:00",
					"hora_hasta": "19:30:00",
					"tipo_sesion": "Entrenamiento",
					"actividad": act,
					"grupo_actividad": grupo,
					"equipo_actividad": equipo_a,
				},
				{
					"dia_semana": "Lunes",
					"hora_desde": "19:00:00",
					"hora_hasta": "20:00:00",
					"tipo_sesion": "Preparacion Fisica",
					"actividad": act,
					"grupo_actividad": grupo,
					"equipo_actividad": equipo_b,
				},
			],
		)
		doc = frappe.get_doc("Espacio", name)
		self.assertEqual(len(doc.horarios), 2)

	def test_hora_hasta_debe_ser_mayor(self) -> None:
		with self.assertRaises(frappe.ValidationError):
			insert_espacio(
				"Cancha Rango Invalido",
				horarios=[
					{
						"dia_semana": "Martes",
						"hora_desde": "19:00:00",
						"hora_hasta": "19:00:00",
					}
				],
			)

	def test_horario_cruza_medianoche(self) -> None:
		name = insert_espacio(
			"Salon Noche Test",
			tipo="Salon",
			horarios=[
				{
					"dia_semana": "Viernes",
					"hora_desde": "22:00:00",
					"hora_hasta": "01:00:00",
					"tipo_sesion": "Entrenamiento",
					"titulo": "Fiesta nocturna",
				}
			],
		)
		doc = frappe.get_doc("Espacio", name)
		self.assertEqual(str(doc.horarios[0].hora_desde)[:5], "22:00")
		self.assertEqual(str(doc.horarios[0].hora_hasta)[:5], "01:00")

	def test_vinculo_equipo_coherente(self) -> None:
		act, grupo, equipo = ensure_actividad_tree(
			"Basquet Spaces Test",
			"Basquet Spaces Test / Masculino",
			"Basquet Spaces Test / Masculino / U11",
		)
		name = insert_espacio(
			"Cancha Vinculo OK",
			horarios=[
				{
					"dia_semana": "Miercoles",
					"hora_desde": "17:00:00",
					"hora_hasta": "18:30:00",
					"actividad": act,
					"grupo_actividad": grupo,
					"equipo_actividad": equipo,
				}
			],
		)
		self.assertTrue(frappe.db.exists("Espacio", name))

	def test_titulo_concatena_tipo_actividad_grupo_equipo(self) -> None:
		act, grupo, equipo = ensure_actividad_tree(
			"Basquet Titulo Spaces",
			"Basquet Titulo Spaces / Masculino",
			"Basquet Titulo Spaces / Masculino / U11",
		)
		name = insert_espacio(
			"Cancha Titulo Concat",
			horarios=[
				{
					"dia_semana": "Viernes",
					"hora_desde": "10:00:00",
					"hora_hasta": "11:00:00",
					"tipo_sesion": "Preparacion Fisica",
					"actividad": act,
					"grupo_actividad": grupo,
					"equipo_actividad": equipo,
					"titulo": "ignorado",
				}
			],
		)
		doc = frappe.get_doc("Espacio", name)
		self.assertEqual(
			doc.horarios[0].titulo,
			"Preparacion Fisica — Basquet Titulo Spaces / Masculino / U11",
		)

	def test_vinculo_equipo_incoherente(self) -> None:
		act_a, grupo_a, _equipo_a = ensure_actividad_tree(
			"Basquet A Spaces",
			"Basquet A Spaces / Azul",
			"Basquet A Spaces / Azul / U13",
		)
		_act_b, _grupo_b, equipo_b = ensure_actividad_tree(
			"Voley B Spaces",
			"Voley B Spaces / Fem",
			"Voley B Spaces / Fem / Primera",
		)
		with self.assertRaises(frappe.ValidationError):
			insert_espacio(
				"Cancha Vinculo Bad",
				horarios=[
					{
						"dia_semana": "Jueves",
						"hora_desde": "17:00:00",
						"hora_hasta": "18:00:00",
						"actividad": act_a,
						"grupo_actividad": grupo_a,
						"equipo_actividad": equipo_b,
					}
				],
			)
