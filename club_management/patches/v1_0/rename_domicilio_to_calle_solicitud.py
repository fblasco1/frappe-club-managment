"""Renombra `domicilio` → `calle` en `Solicitud Asociacion` (portal público)."""

from __future__ import annotations

import frappe

_RENAMES: tuple[tuple[str, str], ...] = (
	("domicilio", "calle"),
	("domicilio_tutor", "calle_tutor"),
)


def execute() -> None:
	doctype = "Solicitud Asociacion"
	for old_name, new_name in _RENAMES:
		if frappe.db.has_column(doctype, old_name) and not frappe.db.has_column(
			doctype, new_name
		):
			frappe.rename_field(doctype, old_name, new_name)
