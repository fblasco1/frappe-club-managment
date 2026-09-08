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
	"""Informe canónico: cobranza imputada por rango de fechas (día = desde=hasta)."""
	return (
		get_recaudacion_unificada_report_columns(filters),
		get_recaudacion_unificada_report_data(filters),
		None,
		None,
		get_recaudacion_unificada_report_summary(filters),
	)
