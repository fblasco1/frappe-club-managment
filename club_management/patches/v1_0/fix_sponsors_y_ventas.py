"""Patch: egresos fuera de Sponsors + sponsor canónico ICDPE-FIN-SPONSOR."""

from __future__ import annotations

from club_management.finance.setup.fix_sponsors_y_ventas import run_fix_sponsors_y_ventas


def execute() -> None:
	run_fix_sponsors_y_ventas()
