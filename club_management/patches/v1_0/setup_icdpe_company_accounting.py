"""Completa defaults contables ICDPE + ítems de servicio."""

from __future__ import annotations

from club_management.setup.icdpe_company import resolve_icdpe_company
from club_management.setup.icdpe_company_accounts import setup_icdpe_company_accounting


def execute() -> None:
	if not resolve_icdpe_company():
		return
	setup_icdpe_company_accounting(create_items=True)
