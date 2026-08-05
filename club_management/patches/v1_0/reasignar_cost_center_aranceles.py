"""Patch: re-imputa el centro de costo de aranceles en facturas históricas.

Las facturas ya emitidas quedaron con las líneas de arancel imputadas al centro de
costo por defecto de la empresa («Administración») en lugar del centro de costo de
la actividad. Este patch corrige la línea (`Sales Invoice Item`) y repone los
asientos (`GL Entry`) del ingreso.

Spec: `club_management/specs/centro_costo_arancel_actividad.md`.
"""

from __future__ import annotations

import frappe

from club_management.members.services.cost_center_backfill import (
	reasignar_cost_center_aranceles,
)


def execute() -> None:
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	reasignar_cost_center_aranceles()
