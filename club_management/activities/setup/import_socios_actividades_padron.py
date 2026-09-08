"""Importación masiva de inscripciones desde CSV del padrón por actividad.

Ejemplo (simulación):

    bench --site <sitio> execute \\
        club_management.activities.setup.import_socios_actividades_padron.run \\
        --kwargs '{"dry_run": True}'

Ejecución real:

    bench --site <sitio> execute \\
        club_management.activities.setup.import_socios_actividades_padron.run \\
        --kwargs '{"dry_run": False, "csv_path": "/ruta/socios_actividades_mapeadas.csv"}'
"""

from __future__ import annotations

from typing import Any

from club_management.activities.services.padron_actividades_link import (
	default_padron_csv_path,
	importar_socios_actividades_padron,
)


def run(
	*,
	dry_run: bool = True,
	csv_path: str | None = None,
	ensure_seed: bool = True,
) -> dict[str, Any]:
	path = csv_path or default_padron_csv_path()
	stats = importar_socios_actividades_padron(
		csv_path=path,
		dry_run=dry_run,
		ensure_seed=ensure_seed,
	)
	_print_resumen(stats, dry_run=dry_run, csv_path=path)
	return stats


def _print_resumen(stats: dict[str, Any], *, dry_run: bool, csv_path: str) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "IMPORT EJECUTADO"
	print("\n" + "=" * 72)
	print(f" INSCRIPCIONES PADRÓN ACTIVIDADES — {mode}")
	print("=" * 72)
	print(f" CSV                             : {csv_path}")
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
