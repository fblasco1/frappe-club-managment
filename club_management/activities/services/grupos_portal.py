"""Listados de grupos y equipos para el portal de inscripción."""

from __future__ import annotations

import frappe


def list_grupos_actividad(actividad: str) -> list[dict[str, str]]:
	"""Grupos/tiras habilitados de una actividad."""
	if not actividad or not frappe.db.table_exists("Grupo Actividad"):
		return []
	rows = frappe.get_all(
		"Grupo Actividad",
		filters={"actividad": actividad, "habilitada": 1},
		fields=["name", "titulo"],
		order_by="orden asc, titulo asc",
	)
	return [{"value": row.name, "label": row.titulo or row.name} for row in rows]


def list_equipos_grupo(grupo_actividad: str) -> list[dict[str, str]]:
	"""Equipos/categorías habilitados dentro de un grupo."""
	if not grupo_actividad or not frappe.db.table_exists("Equipo Actividad"):
		return []
	rows = frappe.get_all(
		"Equipo Actividad",
		filters={"grupo_actividad": grupo_actividad, "habilitada": 1},
		fields=["name", "titulo"],
		order_by="orden asc, titulo asc",
	)
	return [{"value": row.name, "label": row.titulo or row.name} for row in rows]
