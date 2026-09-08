"""Patch GF-6: crea la Holiday List de feriados AR 2026 y la asigna como default.

Idempotente: reutiliza `ensure_holiday_list_argentina`, que crea la lista si no
existe (o completa feriados faltantes) y la asigna como `default_holiday_list`
de las empresas de Argentina que no tengan una elección manual.
"""

from __future__ import annotations

from club_management.finance.setup.feriados_argentina import ensure_holiday_list_argentina


def execute() -> None:
	ensure_holiday_list_argentina(2026)
