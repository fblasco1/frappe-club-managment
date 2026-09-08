"""Ítems y tarifas de aranceles mensuales de básquet ICDPE."""

from __future__ import annotations

from dataclasses import dataclass

from club_management.activities.data.arancel_item_spec import format_arancel_mensual_item_name
from club_management.setup.basquet_cost_center import BASQUET_COST_CENTER

ITEM_MINIBASQUET = "ICDPE-BASQUET-MASCULINO-MINIBASQUET"
ITEM_FORMATIVAS_AZUL = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL"
ITEM_FORMATIVAS_AMARILLA = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA"
ITEM_FORMATIVAS_FLEX = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX"
ITEM_ESCUELITA = "ICDPE-BASQUET-ESCUELITA"
ITEM_FEMENINO_SUP = "ICDPE-BASQUET-FEMENINO-SUP"
# Ítem Desk del equipo «Basquet / Masculino / Amarillo / SUPERIOR» (tarifa informe).
ITEM_MASCULINO_SUPERIOR_AMARILLO = "BASQUET / SUPERIOR / AMARILLO"

# Facturas históricas del concepto «SUPERIOR B» se emitieron por error como vóley federado.
_BASQUET_SUPERIOR_HISTORICAL_ALIASES: dict[str, frozenset[str]] = {
	ITEM_MASCULINO_SUPERIOR_AMARILLO: frozenset(
		{ITEM_MASCULINO_SUPERIOR_AMARILLO, "ICDPE-VOLEY-FEDERADO"}
	),
}

BASQUET_ITEM_RATES: dict[str, float] = {
	ITEM_MINIBASQUET: 28500.0,
	ITEM_FORMATIVAS_AZUL: 28500.0,
	ITEM_FORMATIVAS_AMARILLA: 26500.0,
	ITEM_FORMATIVAS_FLEX: 26500.0,
	ITEM_ESCUELITA: 21000.0,
	ITEM_FEMENINO_SUP: 26500.0,
}


@dataclass(frozen=True)
class BasquetItemSpec:
	item_code: str
	item_name: str
	rate: float
	cost_center: str


BASQUET_ITEM_SPECS: tuple[BasquetItemSpec, ...] = (
	BasquetItemSpec(
		ITEM_MINIBASQUET,
		format_arancel_mensual_item_name("BASQUET", "MASCULINO", "MINIBASQUET"),
		28500.0,
		BASQUET_COST_CENTER,
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_AZUL,
		format_arancel_mensual_item_name("BASQUET", "MASCULINO", "FORMATIVAS", "AZUL"),
		28500.0,
		BASQUET_COST_CENTER,
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_AMARILLA,
		format_arancel_mensual_item_name("BASQUET", "MASCULINO", "FORMATIVAS", "AMARILLA"),
		26500.0,
		BASQUET_COST_CENTER,
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_FLEX,
		format_arancel_mensual_item_name("BASQUET", "MASCULINO", "FORMATIVAS", "FLEX"),
		26500.0,
		BASQUET_COST_CENTER,
	),
	BasquetItemSpec(
		ITEM_ESCUELITA,
		format_arancel_mensual_item_name("BASQUET", "MIXTO", "ESCUELITA"),
		21000.0,
		BASQUET_COST_CENTER,
	),
	BasquetItemSpec(
		ITEM_FEMENINO_SUP,
		format_arancel_mensual_item_name("BASQUET", "FEMENINO", "SUPERIOR"),
		26500.0,
		BASQUET_COST_CENTER,
	),
)


def expand_basquet_arancel_item_codes(item_code: str | None) -> set[str]:
	"""Canónico + alias históricos para informes de pagos por equipo."""
	if not item_code:
		return set()
	aliases = _BASQUET_SUPERIOR_HISTORICAL_ALIASES.get(item_code)
	if aliases:
		return set(aliases)
	return {item_code}


def expand_arancel_item_codes_for_pagos(item_code: str | None) -> set[str]:
	"""Une expansión vóley + básquet para imputación de arancel cobrado."""
	from club_management.activities.data.voley_aranceles_icdpe import (
		expand_voley_arancel_item_codes,
	)

	return expand_voley_arancel_item_codes(item_code) | expand_basquet_arancel_item_codes(item_code)
