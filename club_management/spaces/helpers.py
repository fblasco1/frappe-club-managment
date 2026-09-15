"""Helpers de tests del módulo Spaces."""

from __future__ import annotations

import frappe

from club_management.finance.permissions import ROLE_TESORERIA, ensure_role_tesoreria_exists
from club_management.members.test_helpers import (
	ensure_role_secretaria_exists,
	ensure_role_socio_exists,
)
from club_management.spaces.permissions import ROLE_COORDINACION, ensure_role_coordinacion_exists


def ensure_spaces_roles() -> None:
	ensure_role_coordinacion_exists()
	ensure_role_secretaria_exists()
	ensure_role_tesoreria_exists()
	ensure_role_socio_exists()


def make_role_user(email: str, role: str, first_name: str | None = None) -> str:
	ensure_spaces_roles()
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if role not in {r.role for r in user.roles}:
			user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name or role,
			"send_welcome_email": 0,
			"roles": [{"role": role}],
		}
	).insert(ignore_permissions=True)
	return email


def make_coordinacion_user(email: str = "coordinacion.test@example.com") -> str:
	return make_role_user(email, ROLE_COORDINACION, "Coordinacion")


def make_tesoreria_user(email: str = "tesoreria.spaces@example.com") -> str:
	return make_role_user(email, ROLE_TESORERIA, "Tesoreria")


def make_socio_portal_user(email: str = "socio.spaces@example.com") -> str:
	"""Usuario portal con rol Socio (sin Desk)."""
	ensure_role_socio_exists()
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		user.roles = [r for r in user.roles if r.role == "Socio"]
		if "Socio" not in {r.role for r in user.roles}:
			user.append("roles", {"role": "Socio"})
		user.save(ignore_permissions=True)
		return email
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": "Socio",
			"send_welcome_email": 0,
			"roles": [{"role": "Socio"}],
		}
	).insert(ignore_permissions=True)
	return email


def insert_espacio(
	titulo: str,
	*,
	tipo: str = "Cancha",
	alquilable: int = 0,
	habilitado: int = 1,
	horarios: list[dict] | None = None,
) -> str:
	rows = []
	for row in horarios or []:
		payload = dict(row)
		payload.setdefault("tipo_sesion", "Entrenamiento")
		rows.append(payload)
	doc = frappe.get_doc(
		{
			"doctype": "Espacio",
			"titulo": titulo,
			"tipo": tipo,
			"alquilable": alquilable,
			"habilitado": habilitado,
			"horarios": rows,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_actividad_tree(
	actividad: str,
	grupo: str,
	equipo: str,
) -> tuple[str, str, str]:
	if not frappe.db.exists("Actividad", actividad):
		frappe.get_doc(
			{
				"doctype": "Actividad",
				"titulo": actividad,
				"habilitada": 1,
				"usa_grupos": 1,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Grupo Actividad", grupo):
		frappe.get_doc(
			{
				"doctype": "Grupo Actividad",
				"name": grupo,
				"actividad": actividad,
				"titulo": grupo.rsplit(" / ", 1)[-1],
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
	if not frappe.db.exists("Equipo Actividad", equipo):
		frappe.get_doc(
			{
				"doctype": "Equipo Actividad",
				"name": equipo,
				"grupo_actividad": grupo,
				"titulo": equipo.rsplit(" / ", 1)[-1],
				"habilitada": 1,
			}
		).insert(ignore_permissions=True)
	return actividad, grupo, equipo
