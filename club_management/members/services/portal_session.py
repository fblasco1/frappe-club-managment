"""Resolución del Socio autenticado para APIs del portal."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


SOCIO_ROLE = "Socio"


def get_current_socio() -> Document:
	"""Devuelve el Socio único vinculado a la sesión. Fail closed."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Authentication required"), frappe.AuthenticationError)
	if SOCIO_ROLE not in frappe.get_roles(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	names = frappe.get_all("Socio", filters={"user": user}, pluck="name", limit=2)
	if len(names) != 1:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.get_doc("Socio", names[0])
