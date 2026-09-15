"""Sincroniza canónicos y retira todo el catálogo paralelo ICDPE-ARANCEL-MENSUAL-*."""

from __future__ import annotations

from club_management.activities.services.actividades_icdpe_catalog import (
	sync_actividades_catalogo_icdpe,
)
from club_management.activities.services.basquet_icdpe_items import sync_basquet_icdpe_items
from club_management.activities.services.deporte_icdpe_items import sync_arancel_items
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.data.futbol_aranceles_icdpe import FUTBOL_ITEM_SPECS
from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	OTRAS_ACTIVIDADES_ITEM_SPECS,
)
from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
from club_management.activities.data.voley_aranceles_icdpe import VOLEY_ITEM_SPECS
from club_management.finance.setup.cleanup_legacy_arancel_items import (
	run_cleanup_legacy_arancel_items,
)


def execute() -> None:
	sync_basquet_icdpe_items()
	sync_arancel_items(VOLEY_ITEM_SPECS)
	sync_arancel_items(FUTBOL_ITEM_SPECS)
	sync_arancel_items(PATIN_ITEM_SPECS)
	sync_arancel_items(OTRAS_ACTIVIDADES_ITEM_SPECS)
	sync_actividades_catalogo_icdpe(deshabilitar_legacy=True)
	seed_estructura_actividades_completa(crear_equipos=True)
	run_cleanup_legacy_arancel_items()
