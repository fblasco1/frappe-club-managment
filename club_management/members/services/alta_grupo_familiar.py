"""Alta pública multi-persona: `Solicitud Grupo Familiar` + N `Solicitud Asociacion`.

Una `Solicitud Asociacion` sigue representando a una persona; el trámite familiar
las agrupa bajo un padre con un único `token_seguimiento`. El titular es quien crea
el `Grupo Familiar` al validarse; el resto se incorpora a ese grupo.

Spec: `club_management/specs/portal_alta_grupo_familiar.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.activities.services.actividades_catalog import ensure_actividad_exists
from club_management.members.services.contacto_domicilio import (
	normalize_legacy_solicitud_payload,
)

TRAMITE_DOCTYPE = "Solicitud Grupo Familiar"
SOLICITUD_DOCTYPE = "Solicitud Asociacion"
ACTIVIDAD_DOCTYPE = "Actividad"
GRUPO_ACTIVIDAD_DOCTYPE = "Grupo Actividad"

ROL_TITULAR = "Titular"
ROLES_VALIDOS: frozenset[str] = frozenset(
	{ROL_TITULAR, "Cónyuge", "Hijo", "Padre", "Madre", "Otro"}
)
ROL_FAMILIAR_POR_DEFECTO = "Otro"

MSG_TITULAR_SIN_VALIDAR = "Validá primero la solicitud del titular del grupo"
MSG_FALTA_TITULAR = "El trámite requiere los datos del titular."
MSG_PERSONA_INVALIDA = "Datos de persona inválidos en el trámite."

# El cliente Guest no puede setear estos campos: los gestiona el servidor.
_CAMPOS_BLOQUEADOS: frozenset[str] = frozenset(
	{
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"doctype",
		"workflow_state",
		"token_seguimiento",
		"enviado_desde_ip",
		"socio_generado",
		"user_generado",
		"grupo_familiar_generado",
		"solicitud_grupo",
		"validado_por",
		"validado_en",
		"correccion_solicitada_por",
		"correccion_solicitada_en",
		"observaciones_secretaria",
		"actividades_solicitadas",
		"actividades",
		"rol_en_grupo",
	}
)


def _clean_persona_payload(persona: Any) -> dict[str, Any]:
	if not isinstance(persona, dict):
		frappe.throw(_(MSG_PERSONA_INVALIDA), frappe.ValidationError)
	payload = {k: v for k, v in persona.items() if k not in _CAMPOS_BLOQUEADOS}
	normalize_legacy_solicitud_payload(payload)
	return payload


def _resolve_actividad(nombre: Any) -> str | None:
	"""`name` de una `Actividad` habilitada (acepta título o docname), o `None`."""
	key = str(nombre or "").strip()
	if not key:
		return None
	return ensure_actividad_exists(key)


def _resolve_grupo_actividad(grupo: Any, actividad: str) -> str | None:
	"""Grupo/plan válido y perteneciente a la actividad, o `None`."""
	key = str(grupo or "").strip()
	if not key or not frappe.db.exists(GRUPO_ACTIVIDAD_DOCTYPE, key):
		return None
	row = frappe.db.get_value(
		GRUPO_ACTIVIDAD_DOCTYPE, key, ["actividad", "habilitada"], as_dict=True
	)
	if not row or not row.habilitada or row.actividad != actividad:
		return None
	return key


def _build_actividades_rows(actividades: Any) -> list[dict[str, Any]]:
	"""Filas de `Actividad Solicitada`; descarta lo que no resuelve."""
	if not isinstance(actividades, list):
		return []

	rows: list[dict[str, Any]] = []
	vistas: set[tuple[str, str]] = set()
	for entrada in actividades:
		if isinstance(entrada, str):
			entrada = {"actividad": entrada}
		if not isinstance(entrada, dict):
			continue

		actividad = _resolve_actividad(entrada.get("actividad"))
		if not actividad:
			continue

		grupo = _resolve_grupo_actividad(
			entrada.get("grupo_actividad") or entrada.get("grupo"), actividad
		)
		clave = (actividad, grupo or "")
		if clave in vistas:
			continue
		vistas.add(clave)

		fila: dict[str, Any] = {"actividad": actividad}
		if grupo:
			fila["grupo_actividad"] = grupo
		notas = str(entrada.get("notas") or "").strip()
		if notas:
			fila["notas"] = notas
		rows.append(fila)
	return rows


# Campos del solicitante que se replican como `<campo>_tutor` cuando el menor
# del trámite no trae bloque de responsable propio.
_CAMPOS_REPLICABLES_A_RESPONSABLE: tuple[str, ...] = (
	"nombre",
	"apellido",
	"dni",
	"nacionalidad",
	"fecha_nacimiento",
	"genero",
	"email",
	"telefono_fijo",
	"telefono_movil",
	"calle",
	"numero",
	"piso",
	"departamento",
	"provincia",
	"ciudad",
	"localidad_barrio",
	"codigo_postal",
	"dni_frente",
	"dni_dorso",
	"foto_perfil",
)

_ROL_RESPONSABLE_POR_GENERO: dict[str, str] = {
	"Femenino": "Madre",
	"Masculino": "Padre",
}


def _hidratar_responsable_desde_titular(
	persona: dict[str, Any], titular: dict[str, Any]
) -> dict[str, Any]:
	"""Completa el bloque responsable de un menor con los datos del titular.

	En el wizard familiar el adulto se carga una sola vez: los menores del mismo
	trámite lo reutilizan como responsable. Lo que el portal envíe explícitamente
	tiene prioridad (p. ej. un menor cuyo responsable es el otro progenitor).
	"""
	hidratada = dict(persona)
	for campo in _CAMPOS_REPLICABLES_A_RESPONSABLE:
		destino = f"{campo}_tutor"
		if not str(hidratada.get(destino) or "").strip() and titular.get(campo):
			hidratada[destino] = titular[campo]

	if not str(hidratada.get("rol_tutor") or "").strip():
		hidratada["rol_tutor"] = _ROL_RESPONSABLE_POR_GENERO.get(
			str(titular.get("genero") or ""), "Tutor"
		)
	return hidratada


def _normalize_rol(rol: Any, *, es_titular: bool) -> str:
	if es_titular:
		return ROL_TITULAR
	candidato = str(rol or "").strip()
	return candidato if candidato in ROLES_VALIDOS else ROL_FAMILIAR_POR_DEFECTO


def _insert_solicitud(
	persona: dict[str, Any],
	*,
	tramite_name: str,
	es_titular: bool,
	enviado_desde_ip: str,
	titular: dict[str, Any] | None = None,
) -> Document:
	if not es_titular and titular and persona.get("categoria_solicitada") == "Menor":
		persona = _hidratar_responsable_desde_titular(persona, titular)

	actividades = _build_actividades_rows(persona.get("actividades"))
	sin_actividad = 1 if persona.get("sin_actividad") else 0
	if sin_actividad:
		actividades = []

	payload = _clean_persona_payload(persona)
	payload.pop("actividades", None)
	payload.pop("sin_actividad", None)
	payload.update(
		{
			"doctype": SOLICITUD_DOCTYPE,
			"solicitud_grupo": tramite_name,
			"rol_en_grupo": _normalize_rol(persona.get("rol_en_grupo"), es_titular=es_titular),
			"sin_actividad": sin_actividad,
			"actividades_solicitadas": actividades,
			"enviado_desde_ip": enviado_desde_ip,
		}
	)

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)
	return doc


def crear_alta_grupo(
	data: dict[str, Any],
	*,
	enviado_desde_ip: str = "",
) -> dict[str, Any]:
	"""Crea el trámite familiar completo y devuelve su token público."""
	titular_payload = data.get("titular")
	if not isinstance(titular_payload, dict) or not titular_payload:
		frappe.throw(_(MSG_FALTA_TITULAR), frappe.ValidationError)

	familiares = data.get("familiares") or []
	if not isinstance(familiares, list):
		familiares = []

	titular_normalizado = dict(titular_payload)
	normalize_legacy_solicitud_payload(titular_normalizado)

	tramite = frappe.get_doc(
		{
			"doctype": TRAMITE_DOCTYPE,
			"apellido_principal": str(titular_payload.get("apellido") or "").strip(),
			"email_contacto": str(titular_payload.get("email") or "").strip(),
			"enviado_desde_ip": enviado_desde_ip,
			"cantidad_personas": 1 + len(familiares),
		}
	)
	tramite.insert(ignore_permissions=True)

	titular = _insert_solicitud(
		titular_payload,
		tramite_name=tramite.name,
		es_titular=True,
		enviado_desde_ip=enviado_desde_ip,
	)

	for familiar in familiares:
		_insert_solicitud(
			familiar,
			tramite_name=tramite.name,
			es_titular=False,
			enviado_desde_ip=enviado_desde_ip,
			titular=titular_normalizado,
		)

	tramite.db_set("solicitud_titular", titular.name, update_modified=False)

	return {
		"tramite": tramite.name,
		"token_seguimiento": tramite.token_seguimiento,
		"personas": tramite.cantidad_personas,
	}


def get_tramite_by_token(token: str) -> Document | None:
	"""Trámite cuyo `token_seguimiento` coincide, o `None`."""
	if not (token or "").strip():
		return None
	name = frappe.db.get_value(TRAMITE_DOCTYPE, {"token_seguimiento": token}, "name")
	if not name:
		return None
	return frappe.get_doc(TRAMITE_DOCTYPE, name)


def resumen_personas_tramite(tramite_name: str) -> list[dict[str, Any]]:
	"""Estado por persona, sin PII de los demás integrantes."""
	rows = frappe.get_all(
		SOLICITUD_DOCTYPE,
		filters={"solicitud_grupo": tramite_name},
		fields=["nombre", "apellido", "rol_en_grupo", "workflow_state"],
		order_by="creation asc",
	)
	return [
		{
			"nombre": row.nombre,
			"apellido": row.apellido,
			"rol_en_grupo": row.rol_en_grupo or "",
			"workflow_state": row.workflow_state,
		}
		for row in rows
	]
