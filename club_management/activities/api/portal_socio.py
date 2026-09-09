"""API autenticada de inscripción a actividades para BL-6."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from club_management.activities.services.actividades_catalog import (
	ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
	ensure_actividad_exists,
)
from club_management.activities.services.inscripcion_socio import (
	actividades_resumen_socio,
	inscribir_socio_selecciones,
)


SOCIO_ROLE = "Socio"


def _current_socio() -> frappe.model.document.Document:
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)
	if SOCIO_ROLE not in frappe.get_roles(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	names = frappe.get_all("Socio", filters={"user": user}, pluck="name", limit=2)
	if len(names) != 1:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.get_doc("Socio", names[0])


def _parse_selecciones(raw: Any) -> list[dict[str, Any]]:
	if isinstance(raw, str):
		try:
			raw = json.loads(raw)
		except json.JSONDecodeError:
			raw = None
	if not isinstance(raw, list) or not raw:
		frappe.throw(_("Seleccione al menos una actividad."), frappe.ValidationError)

	result: list[dict[str, Any]] = []
	for row in raw:
		if not isinstance(row, dict):
			frappe.throw(_("Selección inválida."), frappe.ValidationError)
		actividad = ensure_actividad_exists(str(row.get("actividad") or "").strip())
		if not actividad:
			frappe.throw(_("Selección inválida."), frappe.ValidationError)
		tipo_portal = frappe.db.get_value(
			"Actividad",
			actividad,
			"tipo_inscripcion_portal",
		) or "plana"
		grupo = str(row.get("grupo") or row.get("grupo_actividad") or "").strip() or None
		equipo = str(row.get("equipo") or row.get("equipo_actividad") or "").strip() or None
		if equipo:
			frappe.throw(_("Selección inválida."), frappe.ValidationError)
		if tipo_portal in {"plana", "deporte"}:
			if grupo:
				frappe.throw(_("Selección inválida."), frappe.ValidationError)
			result.append({"actividad": actividad})
			continue
		if tipo_portal != "variante_grupo" or not grupo:
			frappe.throw(_("Selección inválida."), frappe.ValidationError)
		grupo_row = frappe.db.get_value(
			"Grupo Actividad",
			grupo,
			["actividad", "habilitada", "portal_socio_elige"],
			as_dict=True,
		)
		if (
			not grupo_row
			or grupo_row.actividad != actividad
			or not grupo_row.habilitada
			or not grupo_row.portal_socio_elige
		):
			frappe.throw(_("Selección inválida."), frappe.ValidationError)
		result.append({"actividad": actividad, "grupo_actividad": grupo})
	return result


def _all_selections_exist(socio: str, selecciones: list[dict[str, Any]]) -> bool:
	for row in selecciones:
		filters: dict[str, Any] = {
			"socio": socio,
			"actividad": row["actividad"],
			"estado": "Activa",
		}
		if row.get("grupo_actividad"):
			filters["grupo_actividad"] = row["grupo_actividad"]
		else:
			filters["grupo_actividad"] = ["is", "not set"]
		if not frappe.db.exists("Inscripcion Actividad", filters):
			return False
	return True


def _response(socio: str, actividades: list[str]) -> dict[str, Any]:
	return {
		"status": "ok",
		"actividades": actividades,
		"actividad_resumen": actividades_resumen_socio(socio),
	}


@frappe.whitelist()
def get_contexto_socio() -> dict[str, Any]:
	"""Devuelve solo el contexto necesario del socio de la sesión."""
	socio = _current_socio()
	return {
		"estado": socio.estado,
		"elegible": socio.estado == ESTADO_SOCIO_PENDIENTE_INSCRIPCION,
	}


@frappe.whitelist()
def get_catalogo_inscripcion() -> list[dict[str, Any]]:
	"""Catálogo portal sin tiras internas ni equipos deportivos."""
	_current_socio()
	actividades = frappe.get_all(
		"Actividad",
		filters={"habilitada": 1},
		fields=["name", "titulo", "tipo_inscripcion_portal"],
		order_by="orden asc, titulo asc",
		limit=0,
	)
	result: list[dict[str, Any]] = []
	for actividad in actividades:
		tipo_portal = actividad.tipo_inscripcion_portal or "plana"
		row: dict[str, Any] = {
			"value": actividad.name,
			"label": actividad.titulo or actividad.name,
			"tipo_inscripcion_portal": tipo_portal,
		}
		if tipo_portal == "variante_grupo":
			row["grupos"] = frappe.get_all(
				"Grupo Actividad",
				filters={
					"actividad": actividad.name,
					"habilitada": 1,
					"portal_socio_elige": 1,
				},
				fields=["name as value", "titulo as label"],
				order_by="orden asc, titulo asc",
				limit=0,
			)
		result.append(row)
	return result


@frappe.whitelist()
def list_inscripciones_propias() -> list[dict[str, Any]]:
	"""Lista exclusivamente las inscripciones visibles para el socio de sesión."""
	_current_socio()
	return frappe.get_list(
		"Inscripcion Actividad",
		filters={"estado": "Activa"},
		fields=[
			"name",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
			"estado",
			"fecha_inscripcion",
		],
		order_by="fecha_inscripcion desc, name asc",
		limit=0,
	)


@frappe.whitelist()
@rate_limit(limit=10, seconds=600)
def confirmar_inscripcion_actividades(selecciones: Any) -> dict[str, Any]:
	"""Confirma actividades planas sin confiar en una identidad del cliente."""
	socio = _current_socio()
	parsed = _parse_selecciones(selecciones)

	if socio.estado == "Activo" and _all_selections_exist(socio.name, parsed):
		return _response(socio.name, actividades_resumen_socio(socio.name).split(", "))
	if socio.estado != ESTADO_SOCIO_PENDIENTE_INSCRIPCION:
		frappe.throw(
			_("La inscripción de actividades no está disponible."),
			frappe.ValidationError,
		)

	actividades = inscribir_socio_selecciones(socio.name, parsed, activar=True)
	return _response(socio.name, actividades)
