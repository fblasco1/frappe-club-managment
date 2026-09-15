"""Re-sincroniza actividades oficiales ICDPE (sitios que ya tenían el seed anterior)."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_icdpe_catalog import sync_actividades_catalogo_icdpe


def execute() -> None:
	if not frappe.db.table_exists("Actividad"):
		return
	sync_actividades_catalogo_icdpe(deshabilitar_legacy=True)
