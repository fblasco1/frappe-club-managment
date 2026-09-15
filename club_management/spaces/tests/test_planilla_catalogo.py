"""Tests catálogo planilla: tipos de evento y orden de columnas."""

from __future__ import annotations

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.planilla import (
	CANCHA_1,
	CANCHA_2,
	COLOR_POR_TIPO,
	ESPACIO_ORDEN_PLANILLA,
	TITULO_PLANILLA,
	categoria_evento,
	color_for_block,
	leyenda_planilla,
	normalize_tipo_sesion,
	sort_espacios_planilla,
)


class TestPlanillaCatalogo(MembersTestCase):
	def test_orden_columnas_espacios(self) -> None:
		espacios = sort_espacios_planilla(
			[
				{"name": "LA CASONA", "titulo": "LA CASONA", "tipo": "Salon"},
				{"name": CANCHA_1, "titulo": CANCHA_1, "tipo": "Cancha"},
				{"name": CANCHA_2, "titulo": CANCHA_2, "tipo": "Cancha"},
				{"name": "SALA ALBAMONTE", "titulo": "SALA ALBAMONTE", "tipo": "Salon"},
			]
		)
		names = [e["name"] for e in espacios]
		self.assertEqual(names[0], CANCHA_1)
		self.assertEqual(names[1], CANCHA_2)
		self.assertLess(names.index("SALA ALBAMONTE"), names.index("LA CASONA"))
		self.assertEqual(espacios[0]["titulo_planilla"], "Cancha 1")
		self.assertEqual(espacios[1]["titulo_planilla"], "Cancha 2")
		self.assertEqual(
			[name for name in names if name in ESPACIO_ORDEN_PLANILLA],
			[CANCHA_1, CANCHA_2, "SALA ALBAMONTE", "LA CASONA"],
		)
		self.assertEqual(TITULO_PLANILLA["PARRILLA - TERRAZA"], "PARRILLA/TERRAZA")

	def test_tipos_evento_y_colores(self) -> None:
		self.assertEqual(normalize_tipo_sesion("Entrenamiento deportivo"), "Entrenamiento")
		self.assertEqual(normalize_tipo_sesion("Preparación física"), "Preparacion Fisica")
		block = {
			"source": "horario",
			"tipo_sesion": "Entrenamiento deportivo",
		}
		self.assertEqual(categoria_evento(block), "Entrenamiento")
		self.assertEqual(color_for_block(block), COLOR_POR_TIPO["Entrenamiento"])
		reserva = {"source": "reserva", "tipo": "Uso interno"}
		self.assertEqual(categoria_evento(reserva), "Alquiler socio")

	def test_leyenda_incluye_seis_tipos(self) -> None:
		labels = {item["label"] for item in leyenda_planilla()}
		self.assertTrue(
			{
				"Entrenamiento",
				"Preparacion Fisica",
				"Alquiler externo",
				"Alquiler socio",
				"Evento club",
				"Bloqueo",
			}.issubset(labels)
		)
