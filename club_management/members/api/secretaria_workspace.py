"""API Desk — panel operativo del workspace Secretaría."""



from __future__ import annotations



import json

from typing import Any



import frappe



from club_management.members.services.secretaria_workspace_panel import (

	get_cuotas_sociales_payload,

	get_panel_lists_payload,

	save_cuotas_sociales_payload,

)



_PANEL_ROLES = {"Secretaria", "System Manager"}





def _ensure_secretaria_panel_access() -> None:

	if frappe.session.user == "Guest":

		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)

	roles = set(frappe.get_roles())

	if not roles.intersection(_PANEL_ROLES):

		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)





@frappe.whitelist()

def get_panel_lists() -> dict[str, Any]:

	"""Listas preview (máx. 5) para el workspace Secretaría."""

	_ensure_secretaria_panel_access()

	return get_panel_lists_payload()





@frappe.whitelist()

def get_cuotas_sociales() -> dict[str, Any]:

	_ensure_secretaria_panel_access()

	if not frappe.has_permission("Club Settings", "read"):

		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)

	return get_cuotas_sociales_payload()





@frappe.whitelist()

def save_cuotas_sociales(rows: str | list[dict[str, Any]]) -> dict[str, Any]:

	_ensure_secretaria_panel_access()

	if not frappe.has_permission("Club Settings", "write"):

		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)

	payload = json.loads(rows) if isinstance(rows, str) else rows

	if not isinstance(payload, list):

		frappe.throw(frappe._("Formato inválido."))

	return save_cuotas_sociales_payload(payload)

