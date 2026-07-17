"""Tests GF-6: último día hábil considerando feriados (lógica pura, sin DB).

Se pasan los feriados de forma explícita (`holidays=`) para no depender de la
Holiday List ni de la base de datos. La resolución desde la Holiday List se
verifica manualmente via `bench execute` (el runner de ERPNext está roto en
este entorno por la precarga de test records).
"""

from __future__ import annotations

import unittest
from datetime import date

from club_management.finance.services.recordatorio_sueldos import (
	get_ultimo_dia_habil_mes,
	is_ultimo_dia_habil,
)


class TestUltimoDiaHabilConFeriados(unittest.TestCase):
	def test_sin_feriados_conserva_comportamiento_previo(self) -> None:
		# 31/01/2026 es sábado → último hábil es 30/01 (viernes).
		self.assertEqual(
			str(get_ultimo_dia_habil_mes("2026-01-15", holidays=[])),
			"2026-01-30",
		)

	def test_ultimo_dia_lunviernes_es_feriado_salta_al_anterior(self) -> None:
		# Julio 2026: 31/07 es viernes. Si es feriado → 30/07 (jueves).
		self.assertEqual(
			str(get_ultimo_dia_habil_mes("2026-07-10", holidays=["2026-07-31"])),
			"2026-07-30",
		)

	def test_feriado_seguido_de_fin_de_semana(self) -> None:
		# Enero 2026: 30 (vie), 31 (sáb). Si 30 es feriado → 29 (jue).
		self.assertEqual(
			str(get_ultimo_dia_habil_mes("2026-01-15", holidays=["2026-01-30", "2026-01-31"])),
			"2026-01-29",
		)

	def test_acepta_objetos_date_en_feriados(self) -> None:
		self.assertEqual(
			str(get_ultimo_dia_habil_mes("2026-07-01", holidays=[date(2026, 7, 31)])),
			"2026-07-30",
		)

	def test_is_ultimo_dia_habil_respeta_feriados(self) -> None:
		# Si 31/07 es feriado, el último hábil es 30/07.
		self.assertFalse(is_ultimo_dia_habil("2026-07-31", holidays=["2026-07-31"]))
		self.assertTrue(is_ultimo_dia_habil("2026-07-30", holidays=["2026-07-31"]))


if __name__ == "__main__":
	unittest.main()
