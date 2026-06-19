"""Carga idempotente de actividades, grupos y equipos."""

from __future__ import annotations

import frappe

from club_management.activities.data.estructura_actividades_club import (
	CATEGORIAS_EQUIPO,
	ESTRUCTURA_CON_GRUPOS,
	GrupoSeed,
)
from club_management.activities.services.actividades_icdpe_catalog import (
	_resolve_actividad_docname,
	resolve_item_name,
	sync_actividades_catalogo_icdpe,
)


def _actividad_docname(titulo: str) -> str | None:
	return _resolve_actividad_docname(titulo) or titulo


def upsert_grupo_actividad(
	actividad_titulo: str,
	grupo: GrupoSeed,
) -> str:
	actividad = _actividad_docname(actividad_titulo)
	if not actividad or not frappe.db.exists("Actividad", actividad):
		frappe.throw(f"Actividad inexistente: {actividad_titulo}")

	name = f"{actividad} / {grupo.titulo}"
	item_link = resolve_item_name(grupo.item_code) if grupo.item_code else None
	payload: dict = {
		"actividad": actividad,
		"titulo": grupo.titulo,
		"orden": grupo.orden,
		"habilitada": 1,
	}
	if item_link:
		payload["item"] = item_link

	if frappe.db.exists("Grupo Actividad", name):
		for key, value in payload.items():
			frappe.db.set_value("Grupo Actividad", name, key, value, update_modified=False)
		frappe.db.set_value("Grupo Actividad", name, "modified", frappe.utils.now(), update_modified=True)
		return name

	doc = frappe.get_doc({"doctype": "Grupo Actividad", "name": name, **payload})
	doc.insert(ignore_permissions=True)
	return doc.name


def upsert_equipo_actividad(grupo_name: str, titulo: str, orden: int) -> str:
	if not frappe.db.exists("Grupo Actividad", grupo_name):
		frappe.throw(f"Grupo inexistente: {grupo_name}")

	name = f"{grupo_name} / {titulo}"
	payload = {
		"grupo_actividad": grupo_name,
		"titulo": titulo,
		"orden": orden,
		"habilitada": 1,
	}
	if frappe.db.exists("Equipo Actividad", name):
		for key, value in payload.items():
			frappe.db.set_value("Equipo Actividad", name, key, value, update_modified=False)
		return name

	doc = frappe.get_doc({"doctype": "Equipo Actividad", "name": name, **payload})
	doc.insert(ignore_permissions=True)
	return name


def seed_estructura_actividades_completa(*, crear_equipos: bool = True) -> dict[str, int]:
	"""Sincroniza catálogo ICDPE + grupos + equipos. Devuelve conteos."""
	sync_actividades_catalogo_icdpe(deshabilitar_legacy=True)

	grupos_creados = 0
	equipos_creados = 0

	for estructura in ESTRUCTURA_CON_GRUPOS:
		actividad = _actividad_docname(estructura.actividad)
		if not actividad:
			continue
		frappe.db.set_value("Actividad", actividad, "usa_grupos", 1, update_modified=False)

		for grupo_seed in estructura.grupos:
			grupo_name = upsert_grupo_actividad(estructura.actividad, grupo_seed)
			grupos_creados += 1

			if not crear_equipos:
				continue
			for idx, categoria in enumerate(CATEGORIAS_EQUIPO):
				upsert_equipo_actividad(grupo_name, categoria, (idx + 1) * 10)
				equipos_creados += 1

	actividades_habilitadas = frappe.db.count("Actividad", {"habilitada": 1})
	return {
		"actividades": actividades_habilitadas,
		"grupos": grupos_creados,
		"equipos": equipos_creados,
	}
