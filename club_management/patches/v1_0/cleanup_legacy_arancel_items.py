"""Patch: apaga Shoe demo y elimina aranceles ARANCEL-MENSUAL deshabilitados."""

from __future__ import annotations

from club_management.finance.setup.cleanup_legacy_arancel_items import (
	run_cleanup_legacy_arancel_items,
)


def execute() -> None:
	run_cleanup_legacy_arancel_items()
