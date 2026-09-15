"""Patch: sincroniza Item.item_name de aranceles al formato canónico."""

from __future__ import annotations

from club_management.activities.services.sync_arancel_item_names import (
	run_sync_arancel_item_names,
)


def execute() -> None:
	run_sync_arancel_item_names()
