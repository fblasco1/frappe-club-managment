"""Ítems y tarifas de aranceles mensuales de vóley ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import ArancelItemSpec

ITEM_VOLEY_TIRA_21500 = "ICDPE-VOLEY-TIRA-21500"
ITEM_VOLEY_TIRA_30500 = "ICDPE-VOLEY-TIRA-30500"
ITEM_VOLEY_ESCUELA_ADOLESCENTE = "ICDPE-VOLEY-ESCUELA-ADOLESCENTE"
ITEM_VOLEY_ESCUELITA_MINIVOLEY = "ICDPE-VOLEY-ESCUELITA-MINIVOLEY"

CC_VOLEY = "Deportes - Voley - ICDPE"

VOLEY_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_VOLEY_TIRA_21500,
		"Arancel mensual vóley — tira U11/U12",
		21500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_TIRA_30500,
		"Arancel mensual vóley — tira formativas y superior",
		30500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_ESCUELA_ADOLESCENTE,
		"Arancel mensual vóley — escuela adolescente",
		21500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_ESCUELITA_MINIVOLEY,
		"Arancel mensual vóley — escuelita minivoley",
		21500.0,
		CC_VOLEY,
	),
)
