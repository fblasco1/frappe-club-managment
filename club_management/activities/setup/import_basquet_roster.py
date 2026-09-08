"""Vincula socios del padrón con categoría y equipo de básquet desde Excel/CSV.

Ejemplo (simulación):

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.activities.setup.import_basquet_roster.run \\
        --kwargs '{"dry_run": True}'

Ejecución real:

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.activities.setup.import_basquet_roster.run \\
        --kwargs '{"dry_run": False, "source_path": "/ruta/JUGADORES BASQUET - PEDRO ECHAGUE.xlsx"}'
"""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.services.basquet_roster_link import (
	default_roster_xlsx_path,
	vincular_roster_basquet,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def run(
	*,
	dry_run: bool = True,
	source_path: str | None = None,
	ensure_seed: bool = True,
) -> dict[str, Any]:
	if ensure_seed:
		seed_estructura_actividades_completa(crear_equipos=True)

	path = source_path or default_roster_xlsx_path()
	stats = vincular_roster_basquet(source_path=path, dry_run=dry_run)
	_print_resumen(stats, dry_run=dry_run, source_path=path)
	return stats


def _print_resumen(stats: dict[str, Any], *, dry_run: bool, source_path: str) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "VINCULACIÓN EJECUTADA"
	print("\n" + "=" * 72)
	print(f" ROSTER BÁSQUET — {mode}")
	print("=" * 72)
	print(f" Archivo                         : {source_path}")
	for key, value in stats.items():
		if key == "errores":
			continue
		print(f" {key:30s}: {value}")
	if stats.get("errores"):
		print("-" * 72)
		print(" Detalle (primeros 25):")
		for err in stats["errores"][:25]:
			print(f"   - {err}")
		remaining = len(stats["errores"]) - 25
		if remaining > 0:
			print(f"   ... y {remaining} más")
	print("=" * 72 + "\n")
