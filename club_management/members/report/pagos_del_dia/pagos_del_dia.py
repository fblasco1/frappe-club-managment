# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

from club_management.members.services.recaudacion_por_concepto import (
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
	"""Legado: misma vista que Cobranza por fechas con un solo día."""
	raw = dict(filters or {})
	fecha = raw.get("fecha") or raw.get("fecha_desde")
	merged = {
		**raw,
		"fecha_desde": fecha,
		"fecha_hasta": fecha,
	}
	return (
		get_recaudacion_unificada_report_columns(merged),
		get_recaudacion_unificada_report_data(merged),
		None,
		None,
		get_recaudacion_unificada_report_summary(merged),
	)
