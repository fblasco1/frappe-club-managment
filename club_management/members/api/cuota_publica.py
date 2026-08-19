"""Endpoint público de valores de cuota social (landing `/socios/cuota`).

Spec: `club_management/specs/valores_cuota_social_page.md`
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.services.cuotas_sociales_public import (
	get_valores_cuota_publica_payload,
)


@frappe.whitelist(allow_guest=True)
def get_valores_cuota() -> dict[str, Any]:
	"""Catálogo público de cuota social: categoría, monto y condición."""
	return get_valores_cuota_publica_payload()
