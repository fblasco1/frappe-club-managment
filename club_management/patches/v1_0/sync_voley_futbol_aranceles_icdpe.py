"""Sincroniza ítems y estructura de aranceles mensuales de vóley y fútbol ICDPE."""

from __future__ import annotations

from club_management.activities.data.futbol_aranceles_icdpe import FUTBOL_ITEM_SPECS
from club_management.activities.data.voley_aranceles_icdpe import VOLEY_ITEM_SPECS
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def execute() -> None:
	sync_arancel_items(VOLEY_ITEM_SPECS)
	sync_arancel_items(FUTBOL_ITEM_SPECS)
	seed_estructura_actividades_completa(crear_equipos=True)
