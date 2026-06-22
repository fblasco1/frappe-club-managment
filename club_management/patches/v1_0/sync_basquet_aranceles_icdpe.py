"""Sincroniza ítems y estructura de aranceles mensuales de básquet ICDPE."""

from __future__ import annotations

from club_management.activities.services.basquet_icdpe_items import (
	retire_packs_clases_items,
	sync_basquet_icdpe_items,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def execute() -> None:
	retire_packs_clases_items()
	sync_basquet_icdpe_items()
	seed_estructura_actividades_completa(crear_equipos=True)
