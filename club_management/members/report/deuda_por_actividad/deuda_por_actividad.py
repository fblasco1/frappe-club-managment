# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.members.report.deuda_por_equipo.deuda_por_equipo import execute as execute_deuda_unificada


def execute(filters: dict[str, Any] | None = None) -> tuple:
	merged = {**(filters or {}), "agrupacion": "Actividad"}
	return execute_deuda_unificada(merged)
