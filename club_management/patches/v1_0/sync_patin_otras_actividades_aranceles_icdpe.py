"""Sincroniza ítems y estructura de patín y otras actividades ICDPE."""

from __future__ import annotations

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def execute() -> None:
	sync_arancel_items(PATIN_ITEM_SPECS)
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)
	seed_estructura_actividades_completa(crear_equipos=True)
