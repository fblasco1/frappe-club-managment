"""Rellena Inscripcion Actividad.socio_nombre para listados existentes."""

from __future__ import annotations

import frappe

from club_management.members.doctype.socio.socio import format_socio_nombre_completo


def execute() -> None:
	if not frappe.db.exists("DocType", "Inscripcion Actividad"):
		return
	if not frappe.db.has_column("Inscripcion Actividad", "socio_nombre"):
		return
	rows = frappe.db.sql(
		"""
		SELECT ia.name, s.nombre_completo, s.apellido, s.nombre
		FROM "tabInscripcion Actividad" ia
		LEFT JOIN "tabSocio" s ON s.name = ia.socio
		WHERE COALESCE(ia.socio_nombre, '') = ''
		""",
		as_dict=True,
	)
	for row in rows:
		nombre = (row.nombre_completo or "").strip() or format_socio_nombre_completo(
			row.apellido, row.nombre
		)
		if nombre:
			frappe.db.set_value(
				"Inscripcion Actividad",
				row.name,
				"socio_nombre",
				nombre,
				update_modified=False,
			)
