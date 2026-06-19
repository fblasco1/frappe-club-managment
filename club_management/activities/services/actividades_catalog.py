"""Catálogo de actividades para portal y Desk."""

from __future__ import annotations

import frappe

from club_management.activities.services.actividades_icdpe_catalog import (
	ACTIVIDADES_CATALOGO_ICDPE,
)

ESTADO_SOCIO_PENDIENTE_INSCRIPCION = "Pendiente de Inscripción"


def list_actividades_portal() -> list[dict[str, str]]:
	"""Actividades habilitadas para UI pública (`value` = `name` del DocType)."""
	if frappe.db.table_exists("tabActividad"):
		rows = frappe.get_all(
			"Actividad",
			filters={"habilitada": 1},
			fields=["name", "titulo"],
			order_by="orden asc, titulo asc",
			limit_page_length=0,
		)
		if rows:
			return [
				{"value": row.name, "label": row.titulo or row.name}
				for row in rows
			]

	return [
		{"value": entry.titulo, "label": entry.titulo}
		for entry in ACTIVIDADES_CATALOGO_ICDPE
	]


def ensure_actividad_exists(titulo_o_name: str) -> str | None:
	"""Resuelve el `name` de `Actividad` si existe y está habilitada."""
	from club_management.activities.services.actividades_icdpe_catalog import (
		_resolve_actividad_docname,
	)

	key = (titulo_o_name or "").strip()
	if not key:
		return None
	name = _resolve_actividad_docname(key)
	if not name:
		return None
	if frappe.db.get_value("Actividad", name, "habilitada"):
		return name
	return None
