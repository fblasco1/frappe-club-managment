"""Patch: catálogo jerárquico de egresos (Item Groups + Items Secretaría)."""

from __future__ import annotations

from club_management.finance.setup.icdpe_finance_items import run_finance_items_seed


def execute() -> None:
	run_finance_items_seed()
