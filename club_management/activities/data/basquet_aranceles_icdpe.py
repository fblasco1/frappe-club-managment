"""Ítems y tarifas de aranceles mensuales de básquet ICDPE."""

from __future__ import annotations

from dataclasses import dataclass

ITEM_MINIBASQUET = "ICDPE-BASQUET-MASCULINO-MINIBASQUET"
ITEM_FORMATIVAS_AZUL = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AZUL"
ITEM_FORMATIVAS_AMARILLA = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-AMARILLA"
ITEM_FORMATIVAS_FLEX = "ICDPE-BASQUET-MASCULINO-FORMATIVAS-FLEX"
ITEM_ESCUELITA = "ICDPE-BASQUET-ESCUELITA"
ITEM_FEMENINO_SUP = "ICDPE-BASQUET-FEMENINO-SUP"

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
		"Arancel mensual básquet masculino — minibásquet",
		28500.0,
		"Deportes - Basquet Masculino - ICDPE",
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_AZUL,
		"Arancel mensual básquet masculino — formativas tira azul",
		28500.0,
		"Deportes - Basquet Masculino - ICDPE",
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_AMARILLA,
		"Arancel mensual básquet masculino — formativas tira amarilla",
		26500.0,
		"Deportes - Basquet Masculino - ICDPE",
	),
	BasquetItemSpec(
		ITEM_FORMATIVAS_FLEX,
		"Arancel mensual básquet masculino — formativas tira flex",
		26500.0,
		"Deportes - Basquet Masculino - ICDPE",
	),
	BasquetItemSpec(
		ITEM_ESCUELITA,
		"Arancel mensual básquet escuelita",
		21000.0,
		"Deportes - Basquet Escuelita - ICDPE",
	),
	BasquetItemSpec(
		ITEM_FEMENINO_SUP,
		"Arancel mensual básquet femenino — superior",
		26500.0,
		"Deportes - Basquet Femenino - ICDPE",
	),
)
