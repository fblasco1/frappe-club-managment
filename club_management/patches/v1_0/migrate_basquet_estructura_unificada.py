"""Seed básquet unificado + migración de inscripciones activas legacy."""

from __future__ import annotations

import frappe

from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)
from club_management.activities.services.migrate_basquet_inscripciones import (
	ensure_basquet_unificado_disponible,
	migrate_basquet_inscripciones_activas,
)


def execute() -> None:
	if not frappe.db.table_exists("Actividad"):
		return
	seed_estructura_actividades_completa(crear_equipos=True)
	ensure_basquet_unificado_disponible()
	stats = migrate_basquet_inscripciones_activas()
	if stats.get("huerfanas"):
		frappe.log_error(
			title="Migración básquet: inscripciones huérfanas",
			message="\n".join(stats.get("errores") or []),
		)
