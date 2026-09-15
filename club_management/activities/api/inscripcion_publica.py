"""API pública de inscripción a actividades tras el pago."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from club_management.activities.services.actividades_catalog import list_actividades_portal
from club_management.activities.services.grupos_portal import (
	list_equipos_grupo,
	list_grupos_actividad,
)
from club_management.activities.services.inscripcion_socio import confirmar_inscripcion_post_pago
from club_management.members.services.solicitud_tokens import verify_pago_token
from club_management.members.workflow.solicitud_asociacion_workflow import STATE_VALIDADA


def _parse_selecciones_arg(raw: Any) -> list[dict[str, Any]] | None:
	"""JSON de selecciones `[{actividad, grupo?, equipo?}]`."""
	if raw is None or raw == "":
		return None
	parsed = raw
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			return None
		try:
			parsed = json.loads(text)
		except json.JSONDecodeError:
			return None
	if not isinstance(parsed, list):
		return None
	selecciones: list[dict[str, Any]] = []
	for row in parsed:
		if isinstance(row, str):
			selecciones.append({"actividad": row.strip()})
			continue
		if isinstance(row, dict) and row.get("actividad"):
			selecciones.append(
				{
					"actividad": str(row.get("actividad", "")).strip(),
					"grupo": str(row.get("grupo") or row.get("grupo_actividad") or "").strip()
					or None,
					"equipo": str(row.get("equipo") or row.get("equipo_actividad") or "").strip()
					or None,
				}
			)
	return selecciones


def _parse_actividades_arg(raw: Any) -> list[str]:
	if raw is None or raw == "":
		return []
	if isinstance(raw, list):
		return [str(x).strip() for x in raw if str(x).strip()]
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			return []
		if text.startswith("["):
			try:
				parsed = json.loads(text)
			except json.JSONDecodeError:
				parsed = None
			if isinstance(parsed, list):
				return [str(x).strip() for x in parsed if str(x).strip()]
		return [part.strip() for part in text.split(",") if part.strip()]
	return []


def _solicitud_from_pago_token(token: str) -> str:
	solicitud_name = verify_pago_token(token)
	if not solicitud_name:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)
	solicitud = frappe.get_doc("Solicitud Asociacion", solicitud_name)
	if solicitud.workflow_state != STATE_VALIDADA or not solicitud.socio_generado:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)
	return solicitud_name


@frappe.whitelist(allow_guest=True)
def get_actividades_inscripcion() -> list[dict[str, str]]:
	"""Catálogo para la página post-pago."""
	return list_actividades_portal()


@frappe.whitelist(allow_guest=True)
def get_grupos_actividad(actividad: str) -> list[dict[str, str]]:
	"""Grupos/tiras de una actividad (portal post-pago)."""
	return list_grupos_actividad(actividad)


@frappe.whitelist(allow_guest=True)
def get_equipos_grupo(grupo_actividad: str) -> list[dict[str, str]]:
	"""Equipos/categorías de un grupo (portal post-pago)."""
	return list_equipos_grupo(grupo_actividad)


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=10, seconds=600)
def confirmar_inscripcion_actividades(
	token: str,
	actividades: Any = None,
	selecciones: Any = None,
) -> dict[str, Any]:
	"""Confirma actividades (y opcionalmente grupo/equipo) y activa al socio."""
	solicitud_name = _solicitud_from_pago_token(token)
	parsed_selecciones = _parse_selecciones_arg(selecciones)
	if parsed_selecciones is not None:
		return confirmar_inscripcion_post_pago(
			solicitud_name, selecciones=parsed_selecciones
		)
	keys = _parse_actividades_arg(actividades)
	return confirmar_inscripcion_post_pago(solicitud_name, actividad_keys=keys)
