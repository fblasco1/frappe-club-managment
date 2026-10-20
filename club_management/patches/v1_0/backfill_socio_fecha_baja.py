"""Completa `Socio.fecha_baja` desde la auditoría en socios ya dados de baja."""

from __future__ import annotations

import frappe
from frappe.utils import getdate


def execute() -> None:
	if not frappe.db.has_column("Socio", "fecha_baja"):
		return
	rows = frappe.db.sql(
		"""
		select name, ultimo_cambio_estado_en
		from "tabSocio"
		where estado = 'Baja' and fecha_baja is null
		""",
		as_dict=True,
	)
	for row in rows:
		if not row.ultimo_cambio_estado_en:
			continue
		frappe.db.set_value(
			"Socio",
			row.name,
			"fecha_baja",
			getdate(row.ultimo_cambio_estado_en),
			update_modified=False,
		)
