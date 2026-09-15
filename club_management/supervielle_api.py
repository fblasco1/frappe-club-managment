from __future__ import annotations

from typing import Any

import frappe

from club_management.integrations.supervielle_webhook import recibir_notificacion_pago as _recibir_notificacion_pago


@frappe.whitelist(allow_guest=True)
def recibir_notificacion_pago() -> dict[str, Any]:
    """Compat: `/api/method/club_management.supervielle_api.recibir_notificacion_pago`."""

    return _recibir_notificacion_pago()

