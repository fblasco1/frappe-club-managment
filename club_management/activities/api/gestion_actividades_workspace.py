"""API Desk — panel catálogo Gestión de Actividades."""

from __future__ import annotations

import json
from typing import Any

import frappe

from club_management.activities.services.gestion_actividades_panel import (
	create_actividad,
	create_arancel_item,
	create_equipo,
	create_grupo,
	get_catalog_payload,
	resolve_item_arancel_rate,
	set_arancel,
	update_actividad,
	update_equipo,
	update_grupo,
)
from club_management.activities.services.gestion_actividades_dashboard import get_dashboard_payload

_PANEL_ROLES = {"Secretaria", "System Manager"}


def _ensure_panel_access() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	roles = set(frappe.get_roles())
	if not roles.intersection(_PANEL_ROLES):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)


@frappe.whitelist()
def get_catalog() -> dict[str, Any]:
	_ensure_panel_access()
	return get_catalog_payload()


@frappe.whitelist()
def get_dashboard(
	reference_date: str | None = None,
	actividad: str | None = None,
) -> dict[str, Any]:
	_ensure_panel_access()
	return get_dashboard_payload(reference_date=reference_date, actividad=actividad or None)


@frappe.whitelist()
def create_actividad_desk(titulo: str, usa_grupos: int = 0) -> dict[str, str]:
	_ensure_panel_access()
	if not frappe.has_permission("Actividad", "create"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return create_actividad(titulo=titulo, usa_grupos=usa_grupos)


@frappe.whitelist()
def create_grupo_desk(actividad: str, titulo: str) -> dict[str, str]:
	_ensure_panel_access()
	if not frappe.has_permission("Grupo Actividad", "create"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return create_grupo(actividad=actividad, titulo=titulo)


@frappe.whitelist()
def create_equipo_desk(grupo_actividad: str, titulo: str) -> dict[str, str]:
	_ensure_panel_access()
	if not frappe.has_permission("Equipo Actividad", "create"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return create_equipo(grupo_actividad=grupo_actividad, titulo=titulo)


@frappe.whitelist()
def set_arancel_desk(
	doctype: str,
	name: str,
	item: str | None = None,
	rate: float | int | str | None = None,
) -> dict[str, Any]:
	_ensure_panel_access()
	if not frappe.has_permission(doctype, "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return set_arancel(doctype=doctype, name=name, item=item, rate=rate)


@frappe.whitelist()
def create_arancel_item_desk(
	item_code: str,
	item_name: str,
	standard_rate: float | int | str = 0,
) -> dict[str, Any]:
	_ensure_panel_access()
	return create_arancel_item(
		item_code=item_code,
		item_name=item_name,
		standard_rate=standard_rate,
	)


@frappe.whitelist()
def get_item_arancel_rate_desk(item: str) -> dict[str, float]:
	_ensure_panel_access()
	return {"rate": resolve_item_arancel_rate(item)}


@frappe.whitelist()
def update_actividad_desk(
	name: str,
	titulo: str | None = None,
	usa_grupos: int | None = None,
	habilitada: int | None = None,
	orden: int | None = None,
	descripcion: str | None = None,
) -> dict[str, Any]:
	_ensure_panel_access()
	if not frappe.has_permission("Actividad", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return update_actividad(
		name=name,
		titulo=titulo,
		usa_grupos=usa_grupos,
		habilitada=habilitada,
		orden=orden,
		descripcion=descripcion,
	)


@frappe.whitelist()
def update_grupo_desk(
	name: str,
	titulo: str | None = None,
	orden: int | None = None,
	habilitada: int | None = None,
) -> dict[str, str]:
	_ensure_panel_access()
	if not frappe.has_permission("Grupo Actividad", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return update_grupo(name=name, titulo=titulo, orden=orden, habilitada=habilitada)


@frappe.whitelist()
def update_equipo_desk(
	name: str,
	titulo: str | None = None,
	orden: int | None = None,
	habilitada: int | None = None,
) -> dict[str, str]:
	_ensure_panel_access()
	if not frappe.has_permission("Equipo Actividad", "write"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	return update_equipo(name=name, titulo=titulo, orden=orden, habilitada=habilitada)


@frappe.whitelist()
def save_arancel_rows(rows: str | list[dict[str, Any]]) -> dict[str, Any]:
	"""Guarda varias filas `{doctype, name, item, rate}` en una llamada."""
	_ensure_panel_access()
	payload = json.loads(rows) if isinstance(rows, str) else rows
	if not isinstance(payload, list):
		frappe.throw(frappe._("Formato inválido."))
	updated = []
	for row in payload:
		doctype = row.get("doctype")
		docname = row.get("name")
		if not doctype or not docname:
			continue
		if not frappe.has_permission(doctype, "write"):
			frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
		updated.append(
			set_arancel(
				doctype=doctype,
				name=docname,
				item=row.get("item") or "",
				rate=row.get("rate") or 0,
			)
		)
	return {"updated": updated}
