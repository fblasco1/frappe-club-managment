"""Endpoints públicos del alta multi-persona (frontend Vercel).

Contrato consumido por el wizard de 3 pasos del portal: catálogo, envío del
trámite familiar y consulta de estado por token. Ningún endpoint expone el
`name` de los documentos (anti-enumeración) ni PII de terceros.

Spec: `club_management/specs/portal_alta_grupo_familiar.md`
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from club_management.members.services.alta_grupo_familiar import (
	ACTIVIDADES_ADHERENTE,
	ROLES_VALIDOS,
	crear_alta_grupo,
	get_tramite_by_token,
	resumen_personas_tramite,
)
from club_management.members.services.actividades_portal import list_actividades_asociacion
from club_management.members.services.google_places import get_places_config_for_portal
from club_management.members.validations import validate_ficha_medica_from_url

CATEGORIAS_SOLICITABLES: tuple[str, ...] = ("Activo", "Menor", "Adherente", "Jubilado")

_CAMPOS_ADJUNTOS = (
	"dni_frente",
	"dni_dorso",
	"foto_perfil",
	"ficha_medica",
	"comprobante_jubilado",
)


def _parse_payload(data: Any) -> dict[str, Any]:
	if isinstance(data, str):
		try:
			data = json.loads(data)
		except json.JSONDecodeError as exc:
			frappe.throw(
				_("Payload inválido (JSON malformado)."), exc=frappe.ValidationError
			)
	if not isinstance(data, dict):
		frappe.throw(_("Payload inválido: se esperaba un objeto."), frappe.ValidationError)
	return data


def _resolve_client_ip() -> str:
	"""IP real del cliente respetando `X-Forwarded-For` detrás del proxy."""
	request = getattr(frappe.local, "request", None)
	if not request:
		return ""

	headers = getattr(request, "headers", None) or {}
	xff = ""
	if headers:
		try:
			xff = headers.get("X-Forwarded-For", "") or ""
		except Exception:
			xff = ""

	if xff:
		primero = xff.split(",")[0].strip()
		if primero:
			return primero

	return getattr(request, "remote_addr", None) or ""


def _validar_adjuntos(personas: list[dict[str, Any]]) -> None:
	"""Valida por magic numbers las fichas médicas de todo el trámite."""
	for persona in personas:
		if not isinstance(persona, dict):
			continue
		ficha = persona.get("ficha_medica")
		if ficha:
			validate_ficha_medica_from_url(ficha)


def _submit_alta_grupo_impl(data: Any) -> dict[str, Any]:
	"""Lógica del alta familiar, sin decoradores HTTP.

	Se expone aparte del wrapper whitelisted porque `@rate_limit` exige un
	request real y un store Redis; los tests unitarios ejercitan esta función
	directamente, igual que en `solicitud_publica.py`.
	"""
	payload = _parse_payload(data)

	titular = payload.get("titular")
	familiares = payload.get("familiares") or []
	if not isinstance(familiares, list):
		familiares = []

	_validar_adjuntos([p for p in [titular, *familiares] if isinstance(p, dict)])

	resultado = crear_alta_grupo(
		{"titular": titular, "familiares": familiares},
		enviado_desde_ip=_resolve_client_ip(),
	)

	# El `name` del trámite no se devuelve: el solicitante opera solo por token.
	return {
		"status": "ok",
		"token_seguimiento": resultado["token_seguimiento"],
		"personas": resultado["personas"],
	}


def _consultar_alta_grupo_impl(token: str) -> dict[str, Any]:
	"""Estado del trámite completo por token, sin PII de terceros."""
	tramite = get_tramite_by_token(token)
	if not tramite:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)

	return {
		"status": "ok",
		"creation": str(tramite.creation),
		"apellido_principal": tramite.apellido_principal,
		"personas": resumen_personas_tramite(tramite.name),
	}


@frappe.whitelist(allow_guest=True)
def get_catalogo_alta() -> dict[str, Any]:
	"""Catálogo que alimenta el wizard: actividades, categorías y Places."""
	return {
		"actividades": list_actividades_asociacion(),
		"categorias": list(CATEGORIAS_SOLICITABLES),
		"roles_grupo": sorted(ROLES_VALIDOS),
		"adjuntos": list(_CAMPOS_ADJUNTOS),
		"actividades_adherente": sorted(ACTIVIDADES_ADHERENTE),
		"places": get_places_config_for_portal(),
	}


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=5, seconds=600)
def submit_alta_grupo(data: Any) -> dict[str, Any]:
	"""Alta pública multi-persona (titular + familiares) en un solo trámite.

	Guest no tiene DocPerm sobre `Solicitud Grupo Familiar` ni sobre
	`Solicitud Asociacion`: este endpoint es el único camino legítimo de
	creación. Rate limit de 5 envíos cada 600 segundos por IP.

	Los adjuntos se suben antes con `frappe.client.upload_file`
	(`allow_guest=True`) y se referencian como URLs `/files/...`.

	Returns:
	    `{"status": "ok", "token_seguimiento": "<hex>", "personas": <int>}`.
	"""
	return _submit_alta_grupo_impl(data)


@frappe.whitelist(allow_guest=True)
def consultar_alta_grupo(token: str) -> dict[str, Any]:
	"""Estado del trámite familiar por `token_seguimiento`."""
	return _consultar_alta_grupo_impl(token)
