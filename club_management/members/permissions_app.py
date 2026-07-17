"""Permisos de acceso a la app en pantalla /desk."""

from __future__ import annotations

import frappe


def has_app_permission() -> bool:
	if frappe.session.user == "Guest":
		return False
	if frappe.session.user == "Administrator":
		return True
	roles = set(frappe.get_roles())
	return bool(roles.intersection({"Secretaria", "Tesoreria", "System Manager"}))
