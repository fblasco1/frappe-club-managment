"""Patch: centro de costo dedicado «Cuotas Sociales» + re-etiquetado histórico.

Crea el centro de costo «Cuotas Sociales», lo fija en el `Item Default` de la cuota
social y re-imputa las facturas ya emitidas (línea + asientos).

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.
"""

from __future__ import annotations

import frappe

from club_management.finance.setup.cuota_social_cost_center import (
	ensure_cuota_social_cost_center,
)
from club_management.members.services.cost_center_backfill import (
	reasignar_cost_center_aranceles,
)


def execute() -> None:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	try:
		ensure_cuota_social_cost_center()
	except Exception:
		frappe.log_error(
			title="add_cuota_social_cost_center — setup", message=frappe.get_traceback()
		)
		return
	reasignar_cost_center_aranceles()
