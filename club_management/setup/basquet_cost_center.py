"""Constantes y helpers del Cost Center único de básquet ICDPE."""

from __future__ import annotations

from club_management.setup.icdpe_company import COMPANY_ABBR

BASQUET_COST_CENTER_NAME = "Deportes - Basquet"
BASQUET_COST_CENTER = f"{BASQUET_COST_CENTER_NAME} - {COMPANY_ABBR}"
BASQUET_COST_CENTER_PARENT = f"Deportes - {COMPANY_ABBR}"

LEGACY_BASQUET_COST_CENTERS: tuple[str, ...] = (
	f"Deportes - Basquet Masculino - {COMPANY_ABBR}",
	f"Deportes - Basquet Escuelita - {COMPANY_ABBR}",
	f"Deportes - Basquet Femenino - {COMPANY_ABBR}",
)
