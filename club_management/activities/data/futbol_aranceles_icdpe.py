"""Ítems y tarifas de aranceles mensuales de fútbol ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import (
	ArancelItemSpec,
	format_arancel_mensual_item_name,
)

ITEM_FUTBOL_FAFI = "ICDPE-FUTBOL-FAFI"
ITEM_FUTBOL_TABI_A = "ICDPE-FUTBOL-TABI-A"
ITEM_FUTBOL_TABI_B = "ICDPE-FUTBOL-TABI-B"

# La escuelita de fútbol opera como el grupo TABI B (no hay cuarto grupo aparte).
GRUPO_FUTBOL_ESCUELITA = "TABI B"

CC_FUTBOL = "Futbol - ICDPE"

FUTBOL_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_FUTBOL_FAFI,
		format_arancel_mensual_item_name("FUTBOL", "FAFI"),
		27500.0,
		CC_FUTBOL,
	),
	ArancelItemSpec(
		ITEM_FUTBOL_TABI_A,
		format_arancel_mensual_item_name("FUTBOL", "TABI A"),
		27500.0,
		CC_FUTBOL,
	),
	ArancelItemSpec(
		ITEM_FUTBOL_TABI_B,
		format_arancel_mensual_item_name("FUTBOL", "ESCUELITA", "TABI B"),
		24500.0,
		CC_FUTBOL,
	),
)
