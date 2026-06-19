"""Aislamiento por usuario para los DocTypes del módulo `Members`.

Implementa los `permission_query_conditions` y `has_permission` que registran
los siguientes hooks (ver `hooks.py`):

- `Socio`               → un `User` con rol `Socio` ve **solo** su propio Socio
                          (Socio.user = current_user).
- `Tutor No Socio`      → ve su propio `Tutor No Socio` (cuando el `User`
                          pertenece a un `Tutor No Socio`) **o** el tutor que
                          encabeza el `Grupo Familiar` del propio Socio
                          (cuando el `User` pertenece a un `Socio` miembro).
- `Grupo Familiar`      → ve el grupo donde figura como miembro (vía
                          `Socio.user`) o como titular `Tutor No Socio` (vía
                          `Tutor No Socio.user`).

`System Manager` y `Secretaria` siempre tienen acceso completo (sin filtro).

Notas:
- Las SQL usan backticks (compatible con MariaDB v10+). Cuando se migre a
  PostgreSQL v14, hay que cambiar a comillas dobles para los identificadores.
- `frappe.db.escape()` cuida el SQL injection en el `user` recibido.
- Las funciones `has_permission` aceptan `doc` como `Document`, `dict` o `str`
  (el nombre): Frappe lo invoca con cualquiera de las tres formas según el
  camino del framework.
"""

from __future__ import annotations

from typing import Any

import frappe


_ROLES_FULL_ACCESS = {"System Manager", "Secretaria"}


def _es_full_access(user: str | None) -> bool:
	if not user or user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return bool(roles & _ROLES_FULL_ACCESS)


def _doc_field(doc: Any, doctype: str, fieldname: str) -> Any:
	"""Lee un campo del documento sin importar si llega como Document/dict/str."""
	if isinstance(doc, str):
		return frappe.db.get_value(doctype, doc, fieldname)
	if hasattr(doc, "get"):
		return doc.get(fieldname)
	return getattr(doc, fieldname, None)


def _doc_name(doc: Any, doctype: str) -> str | None:
	if isinstance(doc, str):
		return doc
	if hasattr(doc, "get"):
		return doc.get("name")
	return getattr(doc, "name", None)


# -----------------------------------------------------------------------------
# Socio
# -----------------------------------------------------------------------------


def socio_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _es_full_access(user):
		return ""
	return f"`tabSocio`.user = {frappe.db.escape(user)}"


def socio_has_permission(doc: Any, ptype: str | None = None, user: str | None = None, **kwargs: Any) -> bool:
	user = user or frappe.session.user
	if _es_full_access(user):
		return True
	socio_user = _doc_field(doc, "Socio", "user")
	return bool(socio_user) and socio_user == user


# -----------------------------------------------------------------------------
# Tutor No Socio
# -----------------------------------------------------------------------------


def tutor_no_socio_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _es_full_access(user):
		return ""
	user_escaped = frappe.db.escape(user)
	return f"""(
		`tabTutor No Socio`.user = {user_escaped}
		OR `tabTutor No Socio`.name IN (
			SELECT t.titular
			FROM `tabTitular de Grupo Familiar` t
			WHERE t.tipo_titular = 'Tutor No Socio'
			  AND t.hasta IS NULL
			  AND t.parent IN (
				SELECT m.parent
				FROM `tabMiembro de Grupo Familiar` m
				WHERE m.socio IN (
					SELECT name FROM `tabSocio` WHERE `user` = {user_escaped}
				)
			)
		)
	)"""


def tutor_no_socio_has_permission(doc: Any, ptype: str | None = None, user: str | None = None, **kwargs: Any) -> bool:
	user = user or frappe.session.user
	if _es_full_access(user):
		return True

	tutor_user = _doc_field(doc, "Tutor No Socio", "user")
	if tutor_user and tutor_user == user:
		return True

	tutor_name = _doc_name(doc, "Tutor No Socio")
	if not tutor_name:
		return False

	socio_names = frappe.db.get_values(
		"Socio", {"user": user}, "name", pluck=True
	) or []
	if not socio_names:
		return False

	row = frappe.db.sql(
		"""
		SELECT 1
		FROM `tabTitular de Grupo Familiar` t
		JOIN `tabMiembro de Grupo Familiar` m ON m.parent = t.parent
		WHERE t.tipo_titular = 'Tutor No Socio'
		  AND t.titular = %(tutor)s
		  AND t.hasta IS NULL
		  AND m.socio IN %(socios)s
		LIMIT 1
		""",
		{"tutor": tutor_name, "socios": tuple(socio_names)},
	)
	return bool(row)


# -----------------------------------------------------------------------------
# Grupo Familiar
# -----------------------------------------------------------------------------


def grupo_familiar_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _es_full_access(user):
		return ""
	user_escaped = frappe.db.escape(user)
	return f"""(
		EXISTS (
			SELECT 1 FROM `tabMiembro de Grupo Familiar` m
			WHERE m.parent = `tabGrupo Familiar`.name
			  AND m.socio IN (
				SELECT name FROM `tabSocio` WHERE `user` = {user_escaped}
			)
		)
		OR EXISTS (
			SELECT 1 FROM `tabTitular de Grupo Familiar` t
			WHERE t.parent = `tabGrupo Familiar`.name
			  AND t.tipo_titular = 'Tutor No Socio'
			  AND t.hasta IS NULL
			  AND t.titular IN (
				SELECT name FROM `tabTutor No Socio` WHERE `user` = {user_escaped}
			)
		)
	)"""


def grupo_familiar_has_permission(doc: Any, ptype: str | None = None, user: str | None = None, **kwargs: Any) -> bool:
	user = user or frappe.session.user
	if _es_full_access(user):
		return True

	grupo_name = _doc_name(doc, "Grupo Familiar")
	if not grupo_name:
		return False

	socio_names = frappe.db.get_values(
		"Socio", {"user": user}, "name", pluck=True
	) or []
	if socio_names:
		row = frappe.db.sql(
			"""
			SELECT 1
			FROM `tabMiembro de Grupo Familiar` m
			WHERE m.parent = %(grupo)s
			  AND m.socio IN %(socios)s
			LIMIT 1
			""",
			{"grupo": grupo_name, "socios": tuple(socio_names)},
		)
		if row:
			return True

	tns_names = frappe.db.get_values(
		"Tutor No Socio", {"user": user}, "name", pluck=True
	) or []
	if tns_names:
		row = frappe.db.sql(
			"""
			SELECT 1
			FROM `tabTitular de Grupo Familiar` t
			WHERE t.parent = %(grupo)s
			  AND t.tipo_titular = 'Tutor No Socio'
			  AND t.hasta IS NULL
			  AND t.titular IN %(tns)s
			LIMIT 1
			""",
			{"grupo": grupo_name, "tns": tuple(tns_names)},
		)
		if row:
			return True

	return False


# -----------------------------------------------------------------------------
# Cargo Socio
# -----------------------------------------------------------------------------


def cargo_socio_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _es_full_access(user):
		return ""
	socio_names = frappe.get_all("Socio", filters={"user": user}, pluck="name")
	if not socio_names:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(name) for name in socio_names)
	return f"`tabCargo Socio`.socio IN ({escaped})"


def cargo_socio_has_permission(
	doc: Any, ptype: str | None = None, user: str | None = None, **kwargs: Any
) -> bool:
	user = user or frappe.session.user
	if _es_full_access(user):
		return True
	socio_name = _doc_field(doc, "Cargo Socio", "socio")
	if not socio_name:
		return False
	socio_user = frappe.db.get_value("Socio", socio_name, "user")
	return bool(socio_user) and socio_user == user


# -----------------------------------------------------------------------------
# Cargo Socio
# -----------------------------------------------------------------------------


def cargo_socio_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user
	if _es_full_access(user):
		return ""
	socio_names = frappe.get_all("Socio", filters={"user": user}, pluck="name")
	if not socio_names:
		return "1=0"
	escaped = ", ".join(frappe.db.escape(name) for name in socio_names)
	return f"`tabCargo Socio`.socio IN ({escaped})"


def cargo_socio_has_permission(
	doc: Any, ptype: str | None = None, user: str | None = None, **kwargs: Any
) -> bool:
	user = user or frappe.session.user
	if _es_full_access(user):
		return True
	socio_name = _doc_field(doc, "Cargo Socio", "socio")
	if not socio_name:
		return False
	socio_user = frappe.db.get_value("Socio", socio_name, "user")
	return bool(socio_user) and socio_user == user
