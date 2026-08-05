"""Patch: limpia Item Groups residuales (Finanzas egresos / Cuotas Sociales)."""

from __future__ import annotations

from club_management.finance.setup.cleanup_residual_item_groups import (
	run_cleanup_residual_item_groups,
)


def execute() -> None:
	run_cleanup_residual_item_groups()
