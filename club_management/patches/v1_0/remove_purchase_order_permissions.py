"""Patch: eliminar el acceso de los roles del club a Purchase Order.

El flujo de egresos pasa a operar exclusivamente con Purchase Invoice.
"""

from __future__ import annotations

from club_management.finance.setup.purchase_order_permissions import (
	remove_purchase_order_club_permissions,
)


def execute() -> None:
	remove_purchase_order_club_permissions()
