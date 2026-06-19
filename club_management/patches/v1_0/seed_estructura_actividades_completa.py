"""Carga actividades ICDPE + grupos/tiras + equipos/categorías del club."""

from __future__ import annotations

import frappe

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def execute() -> None:
	if not frappe.db.table_exists("tabActividad"):
		return
	seed_estructura_actividades_completa(crear_equipos=True)
