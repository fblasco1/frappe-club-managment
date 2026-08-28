"""Resolución de Espacio para partidos importados."""

from __future__ import annotations

import frappe

from club_management.spaces.fixtures.contract import FixturePartido, LOCALIA_LOCAL
from club_management.spaces.import_horarios import CANCHA_3, map_espacio

# Básquet (FeBAMBA GES y fixtures sin espacio explícito) → Cancha 3.
BASQUET_ESPACIO_DEFAULT = CANCHA_3


def resolve_espacio(partido: FixturePartido) -> str | None:
	"""Resuelve nombre de Espacio; None si no se puede mapear."""
	if partido.localia != LOCALIA_LOCAL:
		return None
	if partido.espacio:
		mapped = map_espacio(partido.espacio) or partido.espacio.strip()
		if frappe.db.exists("Espacio", mapped):
			return mapped
		return None
	if frappe.db.exists("Espacio", BASQUET_ESPACIO_DEFAULT):
		return BASQUET_ESPACIO_DEFAULT
	return None
