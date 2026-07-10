"""Import roster básquet CSV Jugadorxs → inscripciones + logs.

Simulación:

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.activities.setup.import_basquet_roster_jugadores.run \\
        --kwargs '{"dry_run": true}'

Ejecución real:

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.activities.setup.import_basquet_roster_jugadores.run \\
        --kwargs '{"dry_run": false}'
"""

from __future__ import annotations

from typing import Any

from club_management.activities.services.basquet_roster_link import (
	default_roster_csv_jugadorxs_path,
	import_roster_jugadores,
)
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)


def run(
	*,
	dry_run: bool = True,
	source_path: str | None = None,
	output_dir: str | None = None,
	ensure_seed: bool = True,
) -> dict[str, Any]:
	if ensure_seed:
		seed_estructura_actividades_completa(crear_equipos=True)

	path = source_path or default_roster_csv_jugadorxs_path()
	stats = import_roster_jugadores(
		source_path=path,
		dry_run=dry_run,
		output_dir=output_dir,
	)
	_print_resumen(stats, dry_run=dry_run, source_path=path)
	return stats


def _print_resumen(stats: dict[str, Any], *, dry_run: bool, source_path: str) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "IMPORT EJECUTADO"
	print("\n" + "=" * 72)
	print(f" ROSTER BÁSQUET JUGADORXS — {mode}")
	print("=" * 72)
	print(f" Archivo                         : {source_path}")
	for key in (
		"total_filas",
		"inscripciones_nuevas",
		"ya_inscriptos",
		"no_padron_sin_dni",
		"no_padron_con_dni",
		"omitidos_duplicado_csv",
	):
		print(f" {key:30s}: {stats.get(key, 0)}")
	print("-" * 72)
	print(" Logs generados:")
	for label, path in (stats.get("log_paths") or {}).items():
		print(f"  {label}: {path}")
	if stats.get("log_paths", {}).get("reporte_html"):
		print("-" * 72)
		print(" Informe HTML (Desk autenticado):")
		print("  /informe-import-roster-basquet")
	if stats.get("errores"):
		print("-" * 72)
		print(" Errores (primeros 15):")
		for err in stats["errores"][:15]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
