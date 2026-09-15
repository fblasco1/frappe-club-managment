# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.services.liquidacion_equipo import (
	get_deuda_por_actividad_data,
	get_deuda_por_actividad_report_columns,
	get_deuda_por_equipo_data,
	get_deuda_report_summary,
	get_report_columns,
)

AGRUPACION_EQUIPO = "Equipo"
AGRUPACION_ACTIVIDAD = "Actividad"


def execute(
	filters: dict[str, Any] | None = None,
) -> tuple[
	list[dict[str, Any]],
	list[dict[str, Any]],
	None,
	None,
	list[dict[str, Any]],
]:
	filters = filters or {}
	agrupacion = (filters.get("agrupacion") or AGRUPACION_EQUIPO).strip()
	if agrupacion == AGRUPACION_ACTIVIDAD:
		data = get_deuda_por_actividad_data(filters)
		return get_deuda_por_actividad_report_columns(), data, None, None, []
	data = get_deuda_por_equipo_data(filters)
	return get_report_columns(), data, None, None, get_deuda_report_summary(data)
