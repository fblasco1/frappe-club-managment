"""Patch: GIMNASIO 1–3 del CSV → canchas existentes; borra duplicados erróneos."""

from __future__ import annotations

from club_management.spaces.import_horarios import (
	consolidate_gimnasio_canchas,
	default_horarios_csv_path,
	import_horarios_csv,
)


def execute() -> None:
	consolidate_gimnasio_canchas()
	path = default_horarios_csv_path()
	if path.exists():
		import_horarios_csv(path, replace_weekdays=True)
