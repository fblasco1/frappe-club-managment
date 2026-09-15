"""Ítems y tarifas de aranceles mensuales de patín ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import (
	ArancelItemSpec,
	format_arancel_mensual_item_name,
)

ITEM_PATIN_AVANZADO = "ICDPE-PATIN-AVANZADO"
ITEM_PATIN_INTERMEDIO = "ICDPE-PATIN-INTERMEDIO"
ITEM_PATIN_MINI = "ICDPE-PATIN-MINI"
ITEM_PATIN_TEENS = "ICDPE-PATIN-TEENS"
ITEM_PATIN_DANZA = "ICDPE-PATIN-DANZA"
ITEM_PATIN_ADULTO = "ICDPE-PATIN-ADULTO"

CC_PATIN = "Patin - ICDPE"

PATIN_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_PATIN_AVANZADO,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "AVANZADO"),
		47500.0,
		CC_PATIN,
	),
	ArancelItemSpec(
		ITEM_PATIN_INTERMEDIO,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "INTERMEDIO"),
		41500.0,
		CC_PATIN,
	),
	ArancelItemSpec(
		ITEM_PATIN_MINI,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "MINI"),
		26000.0,
		CC_PATIN,
	),
	ArancelItemSpec(
		ITEM_PATIN_TEENS,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "TEENS"),
		26000.0,
		CC_PATIN,
	),
	ArancelItemSpec(
		ITEM_PATIN_DANZA,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "DANZA"),
		35000.0,
		CC_PATIN,
	),
	ArancelItemSpec(
		ITEM_PATIN_ADULTO,
		format_arancel_mensual_item_name("PATIN ARTISTICO", "ADULTO"),
		30000.0,
		CC_PATIN,
	),
)
