"""Detección y mensajes de superposición para fixtures / partidos."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.spaces.availability import find_occupancy_conflicts
from club_management.spaces.fixtures.contract import FixturePartido


def format_superposicion_messages(
	partido: FixturePartido,
	espacio: str,
	conflicts: list[dict[str, Any]],
) -> list[str]:
	"""Mensajes legibles para el reporte de import y Coordinación."""
	messages: list[str] = []
	for conflict in conflicts:
		tipo = conflict.get("tipo") or "ocupacion"
		titulo = conflict.get("titulo") or conflict.get("ref") or "?"
		messages.append(
			frappe._("{0} ({1} vs {2}) solapa con {3} «{4}» en {5} {6}").format(
				partido.external_id,
				partido.categoria or partido.motivo,
				partido.rival or "—",
				tipo,
				titulo,
				espacio,
				partido.fecha,
			)
		)
	return messages


def refresh_superposicion_flag(doc: frappe.model.document.Document) -> list[dict[str, Any]]:
	"""Actualiza superposicion_detectada y devuelve conflictos encontrados."""
	if doc.estado != "Confirmada" or not doc.espacio or not doc.fecha:
		doc.superposicion_detectada = 0
		return []
	exclude = None if doc.is_new() else doc.name
	conflicts = find_occupancy_conflicts(
		doc.espacio,
		doc.fecha,
		doc.hora_desde,
		doc.hora_hasta,
		exclude_reserva=exclude,
	)
	doc.superposicion_detectada = 1 if conflicts else 0
	return conflicts
