"""Tests de mapeo e importación del padrón por actividad."""

from __future__ import annotations

import frappe

from club_management.activities.services.padron_actividades_link import (
	es_concepto_federativo,
	es_jubilado_centro,
	parse_actividad_mapeada,
)
from club_management.members.test_helpers import MembersTestCase, insert_socio


class TestPadronActividadesLink(MembersTestCase):
	def test_parse_gimnasia_dos_clases(self) -> None:
		sel = parse_actividad_mapeada("GIMNASIA ARTISTICA 2 VECES POR SEMANA")
		self.assertEqual(sel["actividad"], "Gimnasia Artistica")
		self.assertEqual(sel["grupo"], "2 Clases por Semana")

	def test_parse_basquet_tira_u9(self) -> None:
		sel = parse_actividad_mapeada("BASQUET MASCULINO | TIRA AZUL | U9")
		self.assertEqual(sel["actividad"], "Basquet Masculino")
		self.assertEqual(sel["grupo"], "Tira Azul")
		self.assertEqual(sel["equipo"], "U9")

	def test_parse_voley_superior_a(self) -> None:
		sel = parse_actividad_mapeada("VOLEY | SUPERIOR A")
		self.assertEqual(sel["actividad"], "Voley Femenino")
		self.assertEqual(sel["grupo"], "Tira")
		self.assertEqual(sel["equipo"], "Superior A")

	def test_parse_liga_tabi(self) -> None:
		sel = parse_actividad_mapeada("LIGA TABI")
		self.assertEqual(sel["actividad"], "Futbol")
		self.assertEqual(sel["grupo"], "TABI A")

	def test_parse_patin_avanzado(self) -> None:
		sel = parse_actividad_mapeada("PATIN ARTISTICO | AVANZADO")
		self.assertEqual(sel["actividad"], "Patin Artistico")
		self.assertEqual(sel["grupo"], "Patin Avanzado")

	def test_parse_patin_adulto_preset(self) -> None:
		sel = parse_actividad_mapeada("ADULTO")
		self.assertEqual(sel["actividad"], "Patin Artistico")
		self.assertEqual(sel["grupo"], "Adulto")

	def test_federativa_y_jubilados(self) -> None:
		self.assertTrue(es_concepto_federativo("CUOTA FEDERATIVA DE VOLEY"))
		self.assertTrue(es_jubilado_centro("CENTRO DE JUBILADOS"))

	def test_find_socio_by_nro_padron(self) -> None:
		from club_management.activities.services.padron_actividades_link import (
			find_socio_by_nro_padron,
		)

		socio = insert_socio(dni="70993001", email="padron.act@example.com", estado="Activo")
		meta = frappe.get_meta("Socio")
		if meta.has_field("nro_socio_padron"):
			frappe.db.set_value("Socio", socio.name, "nro_socio_padron", "999001", update_modified=False)
			found = find_socio_by_nro_padron("999001")
			self.assertEqual(found, socio.name)
