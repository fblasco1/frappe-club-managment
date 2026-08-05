"""Patch: seed suppliers + ítems financieros."""

from __future__ import annotations

from club_management.finance.setup.seed_finance_masters import run_seed_finance_masters


def execute() -> None:
	run_seed_finance_masters()
