"""Roles y gates de acceso del módulo Finance."""

from __future__ import annotations

import frappe
from frappe import _

ROLE_TESORERIA = "Tesoreria"
ROLE_SECRETARIA = "Secretaria"
ROLE_SYSTEM_MANAGER = "System Manager"

_ROLES_TESORERIA = frozenset({ROLE_TESORERIA, ROLE_SYSTEM_MANAGER})
_ROLES_CARGA = frozenset({ROLE_SECRETARIA, ROLE_SYSTEM_MANAGER})


def ensure_role_tesoreria_exists() -> None:
	"""Crea el rol Tesoreria con acceso Desk si no existe."""
	if frappe.db.exists("Role", ROLE_TESORERIA):
		return
	frappe.get_doc(
		{"doctype": "Role", "role_name": ROLE_TESORERIA, "desk_access": 1}
	).insert(ignore_permissions=True)


def ensure_tesoreria_access() -> None:
	"""Gate para APIs/reportes de Tesorería (lectura financiera)."""
	if frappe.session.user == "Guest":
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if frappe.session.user == "Administrator":
		return
	if not _ROLES_TESORERIA.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def ensure_carga_rapida_access() -> None:
	"""Gate para registrar ingresos/egresos (Secretaría)."""
	if frappe.session.user == "Guest":
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if frappe.session.user == "Administrator":
		return
	if not _ROLES_CARGA.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def user_has_tesoreria_access() -> bool:
	if frappe.session.user in ("Guest",):
		return False
	if frappe.session.user == "Administrator":
		return True
	return bool(_ROLES_TESORERIA.intersection(frappe.get_roles()))
