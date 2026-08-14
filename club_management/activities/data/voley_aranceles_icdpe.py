"""Ítems y tarifas de aranceles mensuales de vóley ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import (
	ArancelItemSpec,
	format_arancel_mensual_item_name,
)

# Canónicos (un solo etiquetado): Escuela vs Federado.
ITEM_VOLEY_ESCUELA = "ICDPE-VOLEY-ESCUELA"
ITEM_VOLEY_FEDERADO = "ICDPE-VOLEY-FEDERADO"

# Legacy (remap → canónicos; no crear en seed nuevo).
ITEM_VOLEY_TIRA_21500 = "ICDPE-VOLEY-TIRA-21500"
ITEM_VOLEY_TIRA_30500 = "ICDPE-VOLEY-TIRA-30500"
ITEM_VOLEY_ESCUELA_ADOLESCENTE = "ICDPE-VOLEY-ESCUELA-ADOLESCENTE"
ITEM_VOLEY_ESCUELITA_MINIVOLEY = "ICDPE-VOLEY-ESCUELITA-MINIVOLEY"

CC_VOLEY = "Voley - ICDPE"

VOLEY_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(
		ITEM_VOLEY_ESCUELA,
		format_arancel_mensual_item_name("VOLEY", "ESCUELA"),
		21500.0,
		CC_VOLEY,
	),
	ArancelItemSpec(
		ITEM_VOLEY_FEDERADO,
		format_arancel_mensual_item_name("VOLEY", "FEDERADO"),
		30500.0,
		CC_VOLEY,
	),
)

# Remap de códigos viejos → canónicos.
VOLEY_LEGACY_TO_CANONICAL: dict[str, str] = {
	ITEM_VOLEY_TIRA_30500: ITEM_VOLEY_FEDERADO,
	ITEM_VOLEY_TIRA_21500: ITEM_VOLEY_FEDERADO,
	ITEM_VOLEY_ESCUELA_ADOLESCENTE: ITEM_VOLEY_ESCUELA,
	ITEM_VOLEY_ESCUELITA_MINIVOLEY: ITEM_VOLEY_ESCUELA,
	"ICDPE-ARANCEL-MENSUAL-voley": ITEM_VOLEY_FEDERADO,
	"ICDPE-ARANCEL-MENSUAL-VOLEY-GENERAL": ITEM_VOLEY_FEDERADO,
	"ICDPE-ARANCEL-MENSUAL-VOLEY-ESCUELITA": ITEM_VOLEY_ESCUELA,
}


def expand_voley_arancel_item_codes(item_code: str | None) -> set[str]:
	"""Canónico + legacies equivalentes (para informes con facturas sin remapeo)."""
	if not item_code:
		return set()
	codes = {item_code}
	canon = VOLEY_LEGACY_TO_CANONICAL.get(item_code, item_code)
	codes.add(canon)
	for legacy, target in VOLEY_LEGACY_TO_CANONICAL.items():
		if target == canon:
			codes.add(legacy)
	return codes
