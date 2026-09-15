"""Patch: Secretaría puede seleccionar y crear Items (+ select en masters)."""

from __future__ import annotations

from club_management.finance.setup.secretaria_finance_permissions import (
	ensure_secretaria_finance_permissions,
)


def execute() -> None:
	ensure_secretaria_finance_permissions()
