"""Patch GF-6: permisos operativos de Purchase Order (Tesorería y Secretaría)."""

from __future__ import annotations

from club_management.finance.setup.purchase_order_permissions import (
	ensure_purchase_order_permissions,
)


def execute() -> None:
	ensure_purchase_order_permissions()
