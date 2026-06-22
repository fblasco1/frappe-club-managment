"""Ítems y tarifas de aranceles mensuales de fútbol ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import ArancelItemSpec

ITEM_FUTBOL_FAFI = "ICDPE-FUTBOL-FAFI"
ITEM_FUTBOL_TABI_A = "ICDPE-FUTBOL-TABI-A"
ITEM_FUTBOL_TABI_B = "ICDPE-FUTBOL-TABI-B"

# La escuelita de fútbol opera como el grupo TABI B (no hay cuarto grupo aparte).
GRUPO_FUTBOL_ESCUELITA = "TABI B"

CC_FUTBOL = "Deportes - Futbol - ICDPE"

FUTBOL_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_FUTBOL_FAFI,
		"Arancel mensual fútbol — FAFI",
		27500.0,
		CC_FUTBOL,
	),
	ArancelItemSpec(
		ITEM_FUTBOL_TABI_A,
		"Arancel mensual fútbol — TABI A",
		27500.0,
		CC_FUTBOL,
	),
	ArancelItemSpec(
		ITEM_FUTBOL_TABI_B,
		"Arancel mensual fútbol — TABI B (escuelita)",
		24500.0,
		CC_FUTBOL,
	),
)
