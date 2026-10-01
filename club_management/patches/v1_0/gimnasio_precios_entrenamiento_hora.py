"""Gimnasio: Pase Diario → Entrenamiento por hora y precios 49.000 / 24.000 / 31.000 / 5.000.

Spec: `gimnasio_cobro_socios_no_socios.md`.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Item"):
		return
	from club_management.members.services.gimnasio_pases import (
		ensure_gimnasio_pases_items,
		migrar_pase_diario_a_entrenamiento_hora,
		sincronizar_precios_gimnasio,
	)

	migrar_pase_diario_a_entrenamiento_hora()
	try:
		ensure_gimnasio_pases_items()
	except frappe.ValidationError:
		frappe.log_error(title="Patch gimnasio_precios_entrenamiento_hora", message=frappe.get_traceback())
	sincronizar_precios_gimnasio()
