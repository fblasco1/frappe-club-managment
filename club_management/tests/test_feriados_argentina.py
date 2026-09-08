"""Tests GF-6: datos de feriados nacionales de Argentina (lógica pura, sin DB)."""

from __future__ import annotations

import unittest
from datetime import date

from club_management.finance.setup.feriados_argentina import (
	FERIADOS_POR_ANIO,
	holiday_list_name,
)

# Fechas que NO deben figurar (días no laborables de colectividades, no feriados
# nacionales): colectividad judía, islámica y armenia.
FECHAS_COLECTIVIDADES_EXCLUIDAS = {
	"2026-04-24",  # Día de acción por la tolerancia (genocidio armenio)
}
TERMINOS_COLECTIVIDADES = (
	"judía",
	"judia",
	"islám",
	"islam",
	"armeni",
	"pesaj",
	"rosh",
	"kipur",
	"ramadán",
	"ramadan",
	"eid",
)


class TestFeriadosArgentina2026(unittest.TestCase):
	def setUp(self) -> None:
		self.feriados = FERIADOS_POR_ANIO[2026]
		self.fechas = [f for f, _ in self.feriados]

	def test_cantidad_16_feriados_mas_3_no_laborables(self) -> None:
		# 16 feriados nacionales + 3 días no laborables con fines turísticos.
		self.assertEqual(len(self.feriados), 19)

	def test_fechas_unicas_y_dentro_del_anio(self) -> None:
		self.assertEqual(len(self.fechas), len(set(self.fechas)), "Hay fechas duplicadas")
		for f in self.fechas:
			self.assertTrue(f.startswith("2026-"), f"Fecha fuera del año: {f}")

	def test_incluye_feriados_clave(self) -> None:
		for esperado in ("2026-01-01", "2026-07-09", "2026-12-25", "2026-12-08", "2026-03-24", "2026-04-02"):
			self.assertIn(esperado, self.fechas, f"Falta feriado clave {esperado}")

	def test_dia_independencia_es_jueves(self) -> None:
		# 9 de julio de 2026 es jueves (weekday 3).
		self.assertEqual(date(2026, 7, 9).weekday(), 3)
		self.assertIn("2026-07-09", self.fechas)

	def test_puentes_turisticos_2026(self) -> None:
		for puente in ("2026-03-23", "2026-07-10", "2026-12-07"):
			self.assertIn(puente, self.fechas, f"Falta puente turístico {puente}")

	def test_excluye_colectividades(self) -> None:
		for fecha in FECHAS_COLECTIVIDADES_EXCLUIDAS:
			self.assertNotIn(fecha, self.fechas, f"No debe incluirse {fecha} (colectividad)")
		for _fecha, desc in self.feriados:
			low = desc.lower()
			for termino in TERMINOS_COLECTIVIDADES:
				self.assertNotIn(termino, low, f"Descripción de colectividad detectada: {desc!r}")

	def test_holiday_list_name(self) -> None:
		self.assertEqual(holiday_list_name(2026), "Feriados Argentina 2026")


if __name__ == "__main__":
	unittest.main()
