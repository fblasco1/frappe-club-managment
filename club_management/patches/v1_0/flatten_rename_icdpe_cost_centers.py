"""Patch: aplanar Main y renombrar hojas Cost Center ICDPE."""

from __future__ import annotations

from club_management.setup.flatten_rename_icdpe_cost_centers import (
	run_flatten_rename_icdpe_cost_centers,
)


def execute() -> None:
	run_flatten_rename_icdpe_cost_centers()
