"""Patch: elimina Item Groups/Items de fixtures `_Test Item Group*`."""

from __future__ import annotations

from club_management.finance.setup.cleanup_test_item_groups import run_cleanup_test_item_groups


def execute() -> None:
	run_cleanup_test_item_groups()
