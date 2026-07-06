"""Consolida CC básquet legacy → Deportes - Basquet - ICDPE."""

from __future__ import annotations

from club_management.activities.services.basquet_icdpe_items import sync_basquet_icdpe_items
from club_management.setup.consolidate_basquet_cost_centers import consolidate_basquet_cost_centers


def execute() -> dict:
	result = consolidate_basquet_cost_centers()
	sync_basquet_icdpe_items()
	return result
