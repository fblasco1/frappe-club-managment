"""Patch: importa grilla L–V desde fixtures/horarios_lunes_viernes.csv."""

from __future__ import annotations

from club_management.spaces.import_horarios import default_horarios_csv_path, import_horarios_csv


def execute() -> None:
	path = default_horarios_csv_path()
	if not path.exists():
		return
	import_horarios_csv(path, replace_weekdays=True)
