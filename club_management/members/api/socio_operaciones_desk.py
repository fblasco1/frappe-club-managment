"""API Desk — operaciones de Socio e inscripciones (Secretaría, sin pagos online)."""

from __future__ import annotations

import json
from typing import Any

import frappe

from club_management.activities.services.actividades_catalog import list_actividades_portal
from club_management.activities.services.grupos_portal import (
	list_equipos_grupo,
	list_grupos_actividad,
)
from club_management.activities.services.inscripcion_socio import (
	baja_inscripcion_desk,
	inscribir_actividades_desk,
	list_inscripciones_socio_desk,
)
from club_management.members.services.socio_alta_secretaria import (
	crear_socio_desk as crear_socio_desk_service,
	sugerir_categoria_por_fecha_nacimiento,
)
from club_management.members.services.socio_operaciones_secretaria import (
	activar_socio_manual,
	dar_baja_socio,
	ensure_secretaria_operacion_access,
	marcar_moroso,
	omitir_pago_manual,
	reactivar_socio,
	suspender_socio,
)


def _parse_datos_socio(raw: Any) -> dict[str, Any]:
	if raw is None or raw == "":
		frappe.throw(frappe._("Datos de alta inválidos."), frappe.ValidationError)
	parsed = raw
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			frappe.throw(frappe._("Datos de alta inválidos."), frappe.ValidationError)
		parsed = json.loads(text)
	if not isinstance(parsed, dict):
		frappe.throw(frappe._("Datos de alta inválidos."), frappe.ValidationError)
	return parsed


def _parse_selecciones(raw: Any) -> list[dict[str, Any]]:
	if raw is None or raw == "":
		return []
	parsed = raw
	if isinstance(raw, str):
		text = raw.strip()
		if not text:
			return []
		parsed = json.loads(text)
	if not isinstance(parsed, list):
		frappe.throw(frappe._("Formato de selecciones inválido."), frappe.ValidationError)
	result: list[dict[str, Any]] = []
	for row in parsed:
		if isinstance(row, dict) and row.get("actividad"):
			result.append(
				{
					"actividad": str(row.get("actividad", "")).strip(),
					"grupo": str(row.get("grupo") or row.get("grupo_actividad") or "").strip() or None,
					"equipo": str(row.get("equipo") or row.get("equipo_actividad") or "").strip() or None,
				}
			)
	return result


@frappe.whitelist()
def crear_socio_desk(
	datos: Any = None,
	activar_al_guardar: int | str = 0,
	omitir_pago_al_guardar: int | str = 0,
	selecciones: Any = None,
) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	payload = _parse_datos_socio(datos)
	socio_name = crear_socio_desk_service(
		payload,
		activar_al_guardar=bool(int(activar_al_guardar or 0)),
		omitir_pago_al_guardar=bool(int(omitir_pago_al_guardar or 0)),
		selecciones_inscripcion=_parse_selecciones(selecciones) or None,
	)
	estado = frappe.db.get_value("Socio", socio_name, "estado")
	return {"status": "ok", "socio": socio_name, "estado": estado or ""}


@frappe.whitelist()
def sugerir_categoria_desk(fecha_nacimiento: str) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	return {
		"categoria": sugerir_categoria_por_fecha_nacimiento(fecha_nacimiento),
	}


@frappe.whitelist()
def omitir_pago(socio: str, motivo: str | None = None) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = omitir_pago_manual(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def activar_socio(socio: str, motivo: str | None = None) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = activar_socio_manual(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def marcar_socio_moroso(socio: str, motivo: str | None = None) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = marcar_moroso(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def reactivar_socio_desk(socio: str, motivo: str | None = None) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = reactivar_socio(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def suspender_socio_desk(socio: str, motivo: str | None = None) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = suspender_socio(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def dar_baja(socio: str, motivo: str) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	estado = dar_baja_socio(socio, motivo=motivo)
	return {"status": "ok", "estado": estado}


@frappe.whitelist()
def list_actividades_inscripcion_desk() -> list[dict[str, str]]:
	ensure_secretaria_operacion_access()
	return list_actividades_portal()


@frappe.whitelist()
def get_grupos_actividad_desk(actividad: str) -> list[dict[str, str]]:
	ensure_secretaria_operacion_access()
	return list_grupos_actividad(actividad)


@frappe.whitelist()
def get_equipos_grupo_desk(grupo_actividad: str) -> list[dict[str, str]]:
	ensure_secretaria_operacion_access()
	return list_equipos_grupo(grupo_actividad)


@frappe.whitelist()
def inscribir_actividades(socio: str, selecciones: Any = None) -> dict[str, Any]:
	ensure_secretaria_operacion_access()
	payload = _parse_selecciones(selecciones)
	return inscribir_actividades_desk(socio, payload)


@frappe.whitelist()
def list_inscripciones_socio(
	socio: str,
	incluir_bajas: int | str = 0,
) -> list[dict[str, Any]]:
	ensure_secretaria_operacion_access()
	return list_inscripciones_socio_desk(socio, incluir_bajas=bool(int(incluir_bajas or 0)))


@frappe.whitelist()
def baja_inscripcion(inscripcion: str, motivo: str | None = None) -> dict[str, Any]:
	ensure_secretaria_operacion_access()
	return baja_inscripcion_desk(inscripcion, motivo=motivo)


@frappe.whitelist()
def list_becas_socio(socio: str) -> list[dict[str, Any]]:
	ensure_secretaria_operacion_access()
	from club_management.members.services.beca_socio import list_becas_socio_desk

	return list_becas_socio_desk(socio)
