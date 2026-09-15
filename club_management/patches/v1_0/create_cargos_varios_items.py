"""Crea ítems generales para cargos extra (Multa, Cargo varios) + cuenta de ingreso.

Idempotente: reutiliza el setup ICDPE pero solo para el grupo
«ICDPE / Cargos varios», sin tocar el resto del catálogo.
"""

from __future__ import annotations

from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_create_service_items import ensure_cargos_varios_items


def execute() -> None:
	if not resolve_icdpe_company():
		return
	ensure_cargos_varios_items()
