"""Retira duplicados legacy de básquet; deja solo ICDPE-BASQUET-* canónicos."""

from __future__ import annotations

from club_management.activities.services.basquet_icdpe_items import (
	retire_legacy_basquet_arancel_mensual_items,
	sync_basquet_icdpe_items,
)
from club_management.finance.setup.cleanup_legacy_arancel_items import (
	delete_disabled_legacy_arancel_mensual,
	remape_legacy_arancel_links,
)


def execute() -> None:
	sync_basquet_icdpe_items()
	retire_legacy_basquet_arancel_mensual_items()
	remape_legacy_arancel_links()
	# Borra legacy disabled sin facturas ni links (limpia la lista de Producto).
	delete_disabled_legacy_arancel_mensual()
