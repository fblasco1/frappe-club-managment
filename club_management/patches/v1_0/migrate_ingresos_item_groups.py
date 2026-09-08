"""Patch: 4 pilares de Item Group de ingresos + reasignación + cleanup."""

from __future__ import annotations

from club_management.finance.setup.icdpe_income_item_groups import (
	run_ingresos_item_groups_migration,
)


def execute() -> None:
	run_ingresos_item_groups_migration()
