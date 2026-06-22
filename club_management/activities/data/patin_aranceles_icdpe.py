"""Ítems y tarifas de aranceles mensuales de patín ICDPE."""

from __future__ import annotations

from club_management.activities.data.arancel_item_spec import ArancelItemSpec

ITEM_PATIN_AVANZADO = "ICDPE-PATIN-AVANZADO"
ITEM_PATIN_INTERMEDIO = "ICDPE-PATIN-INTERMEDIO"
ITEM_PATIN_MINI = "ICDPE-PATIN-MINI"
ITEM_PATIN_TEENS = "ICDPE-PATIN-TEENS"
ITEM_PATIN_DANZA = "ICDPE-PATIN-DANZA"

CC_PATIN = "Deportes - Patin - ICDPE"

PATIN_ITEM_SPECS: tuple[ArancelItemSpec, ...] = (
	ArancelItemSpec(ITEM_PATIN_AVANZADO, "Arancel mensual patín — avanzado", 42000.0, CC_PATIN),
	ArancelItemSpec(ITEM_PATIN_INTERMEDIO, "Arancel mensual patín — intermedio", 36000.0, CC_PATIN),
	ArancelItemSpec(ITEM_PATIN_MINI, "Arancel mensual patín — mini", 20500.0, CC_PATIN),
	ArancelItemSpec(ITEM_PATIN_TEENS, "Arancel mensual patín — teens", 20500.0, CC_PATIN),
	ArancelItemSpec(ITEM_PATIN_DANZA, "Arancel mensual patín — danza", 29500.0, CC_PATIN),
)
