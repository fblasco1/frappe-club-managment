"""Patch: importa actividades fijas de sábado (Cancha 1 y 2)."""

from __future__ import annotations

from club_management.spaces.import_horarios import (
	default_horarios_sabado_csv_path,
	import_horarios_sabado,
)


def execute() -> None:
	path = default_horarios_sabado_csv_path()
	if not path.exists():
		return
	import_horarios_sabado(path)
