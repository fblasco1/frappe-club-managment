"""Consolida vóley a solo ICDPE-VOLEY-ESCUELA e ICDPE-VOLEY-FEDERADO."""

from __future__ import annotations

from club_management.activities.services.voley_icdpe_items import (
	consolidate_voley_escuela_federado,
)


def execute() -> None:
	consolidate_voley_escuela_federado()
