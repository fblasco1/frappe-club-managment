"""Listado de actividades para el formulario público de asociación (compat)."""

from __future__ import annotations

from club_management.activities.services.actividades_catalog import list_actividades_portal


def list_actividades_asociacion() -> list[dict[str, str]]:
	"""Devuelve actividades seleccionables en el portal (`value` = id de catálogo)."""
	return list_actividades_portal()