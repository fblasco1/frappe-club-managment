# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.members.services.recaudacion_por_concepto import (
	VISTA_PAGOS_DIA,
	get_recaudacion_unificada_report_columns,
	get_recaudacion_unificada_report_data,
	get_recaudacion_unificada_report_summary,
)


def execute(
	filters: dict[str, Any] | None = None,
) -> tuple[
	list[dict[str, Any]],
	list[dict[str, Any]],
	None,
	None,
	list[dict[str, Any]],
]:
	merged = {**(filters or {}), "vista": VISTA_PAGOS_DIA}
	if merged.get("fecha") and not merged.get("fecha_desde"):
		merged["fecha"] = merged["fecha"]
	return (
		get_recaudacion_unificada_report_columns(merged),
		get_recaudacion_unificada_report_data(merged),
		None,
		None,
		get_recaudacion_unificada_report_summary(merged),
	)
