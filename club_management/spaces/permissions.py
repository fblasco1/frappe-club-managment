"""Roles y gates de acceso del módulo Spaces."""

from __future__ import annotations

import frappe
from frappe import _

ROLE_COORDINACION = "Coordinacion"
ROLE_SECRETARIA = "Secretaria"
ROLE_TESORERIA = "Tesoreria"
ROLE_SYSTEM_MANAGER = "System Manager"

_ROLES_ESCRITURA = frozenset({ROLE_COORDINACION, ROLE_SECRETARIA, ROLE_SYSTEM_MANAGER})
_ROLES_LECTURA = frozenset(
	{ROLE_COORDINACION, ROLE_SECRETARIA, ROLE_TESORERIA, ROLE_SYSTEM_MANAGER}
)


def ensure_role_coordinacion_exists() -> None:
	"""Crea el rol Coordinacion con acceso Desk si no existe."""
	if frappe.db.exists("Role", ROLE_COORDINACION):
		return
	frappe.get_doc(
		{"doctype": "Role", "role_name": ROLE_COORDINACION, "desk_access": 1}
	).insert(ignore_permissions=True)


def ensure_spaces_write_access() -> None:
	"""Gate para crear/editar Espacio y Reserva Espacio."""
	if frappe.session.user == "Guest":
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if frappe.session.user == "Administrator":
		return
	if not _ROLES_ESCRITURA.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def ensure_spaces_read_access() -> None:
	"""Gate de lectura de Spaces (incluye Tesorería)."""
	if frappe.session.user == "Guest":
		frappe.throw(_("No autorizado"), frappe.PermissionError)
	if frappe.session.user == "Administrator":
		return
	if not _ROLES_LECTURA.intersection(frappe.get_roles()):
		frappe.throw(_("No autorizado"), frappe.PermissionError)


def user_has_spaces_write_access() -> bool:
	if frappe.session.user == "Guest":
		return False
	if frappe.session.user == "Administrator":
		return True
	return bool(_ROLES_ESCRITURA.intersection(frappe.get_roles()))
