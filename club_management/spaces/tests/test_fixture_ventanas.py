"""Tests ventanas de ocupación de partidos (warm-up / duración)."""

from __future__ import annotations

from club_management.members.test_helpers import MembersTestCase
from club_management.spaces.fixtures.parse import normalize_partido


class TestFixtureVentanasPartido(MembersTestCase):
	def test_liga_metro_warmup_60_y_duracion_90(self) -> None:
		# Kickoff 21:15 → bloquea 20:15–22:45
		result = normalize_partido(
			{
				"source": "febamba_ges",
				"external_id": "lm-001",
				"fecha": "2026-08-28",
				"hora": "21:15",
				"categoria": "Liga Metro",
				"rival": "CLUB SPORTIVO ESCOBAR LM",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.hora_desde, "20:15:00")
		self.assertEqual(result.hora_hasta, "22:45:00")

	def test_superior_b_warmup_30(self) -> None:
		# Kickoff 21:30 → bloquea desde 21:00; duración partido 90 min → 23:00
		result = normalize_partido(
			{
				"source": "febamba_ges",
				"external_id": "supb-001",
				"fecha": "2026-08-26",
				"hora": "21:30",
				"categoria": "SUP",
				"tira": "B",
				"rival": "CIRCULO URQUIZA",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.hora_desde, "21:00:00")
		self.assertEqual(result.hora_hasta, "23:00:00")

	def test_formativas_duracion_90(self) -> None:
		# Kickoff 09:00 → 09:00–10:30
		result = normalize_partido(
			{
				"source": "febamba_ges",
				"external_id": "form-001",
				"fecha": "2026-09-06",
				"hora": "09:00",
				"categoria": "U17",
				"tira": "AZUL",
				"rival": "Rival",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		self.assertEqual(result.hora_desde, "09:00:00")
		self.assertEqual(result.hora_hasta, "10:30:00")

	def test_hora_hasta_explicita_respeta_rango_sin_warmup(self) -> None:
		result = normalize_partido(
			{
				"source": "febamba_ges",
				"external_id": "exp-001",
				"fecha": "2026-09-06",
				"hora": "20:00",
				"hora_hasta": "21:00",
				"categoria": "U15",
				"localia": "Local",
			}
		)
		self.assertNotIsInstance(result, str)
		assert not isinstance(result, str)
		# Con hasta explícita no aplica reglas de categoría (kickoff = desde)
		self.assertEqual(result.hora_desde, "20:00:00")
		self.assertEqual(result.hora_hasta, "21:00:00")
