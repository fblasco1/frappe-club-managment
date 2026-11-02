"""Crea el ítem Entrenamiento Personalizado del gimnasio (30.000).

Spec: `gimnasio_cobro_socios_no_socios.md`.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Item"):
		return
	try:
		from club_management.members.services.gimnasio_pases import (
			ensure_gimnasio_pases_items,
			sincronizar_precios_gimnasio,
		)

		ensure_gimnasio_pases_items()
		sincronizar_precios_gimnasio()
	except Exception:
		frappe.log_error(
			title="Patch gimnasio_entrenamiento_personalizado",
			message=frappe.get_traceback(),
		)
