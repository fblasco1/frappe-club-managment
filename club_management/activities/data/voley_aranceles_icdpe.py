"""Ítems y tarifas de aranceles mensuales de vóley ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import (
	ArancelItemSpec,
	format_arancel_mensual_item_name,
)

ITEM_VOLEY_TIRA_21500 = "ICDPE-VOLEY-TIRA-21500"
ITEM_VOLEY_TIRA_30500 = "ICDPE-VOLEY-TIRA-30500"
ITEM_VOLEY_ESCUELA_ADOLESCENTE = "ICDPE-VOLEY-ESCUELA-ADOLESCENTE"
ITEM_VOLEY_ESCUELITA_MINIVOLEY = "ICDPE-VOLEY-ESCUELITA-MINIVOLEY"

CC_VOLEY = "Voley - ICDPE"

VOLEY_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_VOLEY_TIRA_21500,
		format_arancel_mensual_item_name("VOLEY", "FEMENINO", "TIRA", "U11-U12"),
		21500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_TIRA_30500,
		format_arancel_mensual_item_name("VOLEY", "FEMENINO", "TIRA", "FORMATIVAS-SUPERIOR"),
		30500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_ESCUELA_ADOLESCENTE,
		format_arancel_mensual_item_name("VOLEY", "FEMENINO", "ESCUELA ADOLESCENTE"),
		21500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_ESCUELITA_MINIVOLEY,
		format_arancel_mensual_item_name("VOLEY", "FEMENINO", "ESCUELITA", "MINIVOLEY"),
		21500.0,
		CC_VOLEY,
	),
)
