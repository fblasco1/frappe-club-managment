"""Patch: permisos de Purchase Invoice (Secretaría draft-only, Tesorería full)."""

from __future__ import annotations

from club_management.finance.setup.purchase_invoice_permissions import (
	ensure_purchase_invoice_permissions,
)


def execute() -> None:
	ensure_purchase_invoice_permissions()
