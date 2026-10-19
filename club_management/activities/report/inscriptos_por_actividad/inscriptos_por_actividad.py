# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.activities.services.reporte_inscriptos_actividad import (
	get_inscriptos_por_actividad_data,
	get_report_columns,
)


def execute(
	filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	return get_report_columns(), get_inscriptos_por_actividad_data(filters)
