"""Datos críticos incompletos en Socio (advertencia Secretaría, sin bloquear edición)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

ATTACH_FIELDS: tuple[tuple[str, str], ...] = (
	("foto_perfil", _("Foto de perfil")),
	("dni_frente", _("DNI - frente")),
	("dni_dorso", _("DNI - dorso")),
	("ficha_medica", _("Ficha médica")),
)

CONTACT_FIELDS: tuple[tuple[str, str], ...] = (
	("email", _("Email")),
	("telefono_movil", _("Teléfono móvil")),
)

PERSONAL_FIELDS: tuple[tuple[str, str], ...] = (
	("nombre", _("Nombre")),
	("apellido", _("Apellido")),
	("dni", _("DNI")),
	("nacionalidad", _("Nacionalidad")),
	("fecha_nacimiento", _("Fecha de nacimiento")),
	("genero", _("Género")),
	("categoria", _("Categoría")),
)

DOMICILIO_FIELDS: tuple[tuple[str, str], ...] = (
	("calle", _("Calle")),
	("ciudad", _("Ciudad")),
	("provincia", _("Provincia")),
)

MENOR_FIELDS: tuple[tuple[str, str], ...] = (
	("tipo_tutor", _("Tipo de tutor")),
	("tutor", _("Tutor")),
)


def _valor_vacio(value: Any) -> bool:
	if value is None:
		return True
	if isinstance(value, str):
		return not value.strip()
	return False


def usuario_puede_edicion_parcial_secretaria(user: str | None = None) -> bool:
	"""True si el usuario puede guardar un Socio existente con datos críticos incompletos."""
	username = user or frappe.session.user
	if not username or username == "Guest":
		return False
	roles = set(frappe.get_roles(username))
	return bool(roles & {"Secretaria", "System Manager"})


def get_datos_criticos_faltantes_socio(socio: dict[str, Any] | frappe.Document) -> list[dict[str, str]]:
	"""Lista campos críticos vacíos con etiquetas para Desk."""
	data = socio if isinstance(socio, dict) else socio.as_dict()
	faltantes: list[dict[str, str]] = []

	def _append(fields: tuple[tuple[str, str], ...]) -> None:
		for fieldname, label in fields:
			if _valor_vacio(data.get(fieldname)):
				faltantes.append({"fieldname": fieldname, "label": label})

	_append(PERSONAL_FIELDS)
	_append(CONTACT_FIELDS)
	_append(DOMICILIO_FIELDS)
	_append(ATTACH_FIELDS)
	if data.get("categoria") == "Jubilado":
		if _valor_vacio(data.get("comprobante_jubilado")):
			faltantes.append({"fieldname": "comprobante_jubilado", "label": _("Comprobante jubilado")})
	if data.get("categoria") == "Menor":
		_append(MENOR_FIELDS)
	return faltantes


def aplicar_edicion_parcial_secretaria(doc: frappe.Document) -> None:
	"""Permite guardar ediciones Desk sin bloquear por mandatory / tutor faltante."""
	if doc.is_new() or not usuario_puede_edicion_parcial_secretaria():
		return
	doc.flags.ignore_mandatory = True
