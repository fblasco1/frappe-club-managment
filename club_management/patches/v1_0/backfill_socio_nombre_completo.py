"""Rellena `nombre_completo` en socios existentes (Apellido, Nombre/s)."""

from __future__ import annotations

import frappe

from club_management.members.doctype.socio.socio import format_socio_nombre_completo


def execute() -> None:
	if not frappe.db.has_column("Socio", "nombre_completo"):
		return

	for row in frappe.get_all("Socio", fields=["name", "nombre", "apellido"]):
		label = format_socio_nombre_completo(row.apellido, row.nombre)
		frappe.db.set_value("Socio", row.name, "nombre_completo", label, update_modified=False)
