"""Patch: custom fields financieros (club_concepto)."""

from __future__ import annotations

from club_management.finance.setup.seed_finance_masters import ensure_finance_custom_fields


def execute() -> None:
	ensure_finance_custom_fields()
