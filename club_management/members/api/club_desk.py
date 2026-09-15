"""API Desk — utilidades transversales de navegación del club."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.members.services.club_desk_search import search_socios

_PANEL_ROLES = {"Secretaria", "System Manager"}


def _ensure_panel_access() -> None:
	if frappe.session.user == "Guest":
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	roles = set(frappe.get_roles())
	if not roles.intersection(_PANEL_ROLES):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)


@frappe.whitelist()
def search_socio_desk(query: str = "", limit: int = 8) -> list[dict[str, Any]]:
	_ensure_panel_access()
	return search_socios(query=query, limit=limit)
