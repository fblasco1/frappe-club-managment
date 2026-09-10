"""API autenticada del perfil del socio (lectura y actualización acotada)."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from club_management.members.services.portal_session import get_current_socio


_PERFIL_FIELDS = (
	"numero_socio",
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
	"estado",
	"categoria",
	"actividad",
	"fecha_ingreso",
	"fecha_alta",
)

EDITABLE_FIELDS = frozenset(
	{
		"nombre",
		"apellido",
		"nacionalidad",
		"fecha_nacimiento",
		"genero",
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
	}
)

_BLOCKED_FIELDS = frozenset(_PERFIL_FIELDS) - EDITABLE_FIELDS | {
	"foto_perfil",
	"dni_frente",
	"dni_dorso",
	"ficha_medica",
	"comprobante_jubilado",
	"user",
	"name",
	"estado",
	"categoria",
	"actividad",
	"fecha_ingreso",
	"fecha_alta",
	"numero_socio",
	"dni",
	"email",
}


def _serialize_date(value: Any) -> str | None:
	if not value:
		return None
	return str(value)


def _perfil_payload(socio: Any) -> dict[str, Any]:
	foto = (socio.foto_perfil or "").strip()
	payload: dict[str, Any] = {field: socio.get(field) for field in _PERFIL_FIELDS}
	payload["fecha_nacimiento"] = _serialize_date(payload.get("fecha_nacimiento"))
	payload["fecha_ingreso"] = _serialize_date(payload.get("fecha_ingreso"))
	payload["fecha_alta"] = _serialize_date(payload.get("fecha_alta"))
	payload["tiene_foto"] = bool(foto)
	return payload


def _parse_data(data: Any) -> dict[str, Any]:
	if data is None:
		return {}
	if isinstance(data, str):
		data = json.loads(data) if data.strip() else {}
	if not isinstance(data, dict):
		frappe.throw(_("Invalid data"), frappe.ValidationError)
	return data


def _normalize_comparable(value: Any) -> str:
	if value is None:
		return ""
	return str(value).strip()


@frappe.whitelist()
def get_perfil_socio() -> dict[str, Any]:
	"""Datos personales del socio de la sesión, sin adjuntos sensibles."""
	return _perfil_payload(get_current_socio())


@frappe.whitelist()
def update_perfil_socio(data: Any = None) -> dict[str, Any]:
	"""Actualiza campos personales whitelisted del socio de sesión."""
	payload = _parse_data(data)
	socio = get_current_socio()

	for key, value in payload.items():
		if key in EDITABLE_FIELDS:
			continue
		if key in _BLOCKED_FIELDS:
			current = _normalize_comparable(socio.get(key))
			incoming = _normalize_comparable(value)
			if incoming != current:
				frappe.throw(
					_("No podés modificar el campo {0} desde el portal").format(key),
					frappe.ValidationError,
				)

	changed = False
	for field in EDITABLE_FIELDS:
		if field not in payload:
			continue
		new_value = payload[field]
		if field == "fecha_nacimiento" and new_value:
			new_value = str(new_value)[:10]
		if _normalize_comparable(socio.get(field)) == _normalize_comparable(new_value):
			continue
		socio.set(field, new_value)
		changed = True

	if changed:
		socio.flags.ignore_permissions = True
		socio.save()

	socio.reload()
	return _perfil_payload(socio)


@frappe.whitelist()
def get_foto_perfil_path() -> str:
	"""Ruta privada de la foto del socio de sesión (solo para el BFF)."""
	socio = get_current_socio()
	path = (socio.foto_perfil or "").strip()
	if not path:
		frappe.throw(_("Not Found"), frappe.DoesNotExistError)
	return path


def assert_foto_path_pertenece_al_socio(path: str) -> None:
	"""Impide servir un blob que no sea la foto_perfil del socio de sesión."""
	socio = get_current_socio()
	propia = (socio.foto_perfil or "").strip()
	candidate = (path or "").strip()
	if not propia or not candidate or propia != candidate:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
