"""Normaliza `Socio.solicitud_origen` al migrar de Data → Link.

Si hay valores huérfanos (string que no existe como `Solicitud Asociacion.name`),
se limpian a NULL para evitar referencias rotas.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	# Solo actuar si la columna existe (defensivo ante instalaciones parciales).
	cols = set(frappe.db.get_table_columns("Socio"))
	if "solicitud_origen" not in cols:
		return

	# Limpiar referencias que no existen como Solicitud Asociacion.
	orphans = frappe.db.sql(
		"""
		select s.name
		from `tabSocio` s
		left join `tabSolicitud Asociacion` sol
			on sol.name = s.solicitud_origen
		where coalesce(s.solicitud_origen, '') != ''
		  and sol.name is null
		""",
		as_dict=True,
	)
	if not orphans:
		return

	names = [row["name"] for row in orphans]
	frappe.db.set_value(
		"Socio",
		{"name": ["in", names]},
		"solicitud_origen",
		None,
		update_modified=False,
	)

