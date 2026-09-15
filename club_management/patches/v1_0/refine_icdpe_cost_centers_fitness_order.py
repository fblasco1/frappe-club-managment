"""Patch: CrossFit/Funcional → Fitness; Administración y Cuotas arriba en la raíz."""

from __future__ import annotations

from club_management.setup.flatten_rename_icdpe_cost_centers import (
	run_flatten_rename_icdpe_cost_centers,
)


def execute() -> None:
	# Idempotente: re-aplica fitness + orden aunque el flatten previo ya corrió.
	run_flatten_rename_icdpe_cost_centers()
