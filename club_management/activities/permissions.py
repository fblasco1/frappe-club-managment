"""Aislamiento de inscripciones para el portal autenticado del socio."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


_FULL_ACCESS_ROLES = {"System Manager", "Secretaria"}


def _has_full_access(user: str) -> bool:
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & _FULL_ACCESS_ROLES)


def _is_socio_user(user: str) -> bool:
	return user != "Guest" and "Socio" in frappe.get_roles(user)


def session_socio_name(user: str | None = None) -> str | None:
	"""Socio único vinculado al usuario de sesión, o None si el vínculo no es exacto."""
	user = user or frappe.session.user
	if not _is_socio_user(user):
		return None
	names = frappe.get_all("Socio", filters={"user": user}, pluck="name", limit=2)
	if len(names) != 1:
		return None
	return names[0]


def _doc_socio(doc: Any) -> Any:
	if isinstance(doc, str):
		return frappe.db.get_value("Inscripcion Actividad", doc, "socio")
	if hasattr(doc, "get"):
		return doc.get("socio")
	return getattr(doc, "socio", None)


def assert_inscripcion_socio_matches_session(doc: Any, user: str | None = None) -> None:
	"""Impide persistir una inscripción para otro socio, incluso con ignore_permissions."""
	user = user or frappe.session.user
	if _has_full_access(user):
		return
	socio = session_socio_name(user)
	if not socio or _doc_socio(doc) != socio:
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def inscripcion_actividad_query_conditions(user: str | None = None) -> str:
	"""Limita los listados al Socio vinculado con el usuario de sesión (PostgreSQL)."""
	user = user or frappe.session.user
	if _has_full_access(user):
		return ""
	if not _is_socio_user(user):
		return "1 = 0"
	escaped_user = frappe.db.escape(user)
	return (
		'"tabInscripcion Actividad"."socio" IN ('
		'SELECT "name" FROM "tabSocio" '
		f'WHERE "user" = {escaped_user}'
		")"
	)


def inscripcion_actividad_has_permission(
	doc: Any,
	ptype: str | None = None,
	user: str | None = None,
	**kwargs: Any,
) -> bool:
	"""Impide lectura directa de inscripciones pertenecientes a otro socio."""
	user = user or frappe.session.user
	if _has_full_access(user):
		return True
	if not _is_socio_user(user) or ptype not in (None, "read", "select"):
		return False

	socio = _doc_socio(doc)
	if not socio:
		return False
	return session_socio_name(user) == socio
