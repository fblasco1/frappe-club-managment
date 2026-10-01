"""Gimnasio: condición socio en grupos, admite no socios e ítems de Quincena / Entrenamiento por hora.

Spec: `gimnasio_cobro_socios_no_socios.md`.
"""

from __future__ import annotations

import frappe

from club_management.activities.data.estructura_actividades_club import ESTRUCTURA_GIMNASIO_FITNESS
from club_management.activities.services.actividades_icdpe_catalog import _resolve_actividad_docname


def execute() -> None:
	actividad = _resolve_actividad_docname(ESTRUCTURA_GIMNASIO_FITNESS.actividad)
	if actividad and frappe.db.exists("Actividad", actividad):
		frappe.db.set_value("Actividad", actividad, "admite_no_socios", 1, update_modified=False)
		for grupo in ESTRUCTURA_GIMNASIO_FITNESS.grupos:
			name = f"{actividad} / {grupo.titulo}"
			if grupo.condicion_socio and frappe.db.exists("Grupo Actividad", name):
				frappe.db.set_value(
					"Grupo Actividad", name, "condicion_socio", grupo.condicion_socio, update_modified=False
				)

	if not frappe.db.exists("DocType", "Item"):
		return
	try:
		from club_management.members.services.gimnasio_pases import ensure_gimnasio_pases_items

		ensure_gimnasio_pases_items()
	except frappe.ValidationError:
		frappe.log_error(title="Patch gimnasio_cobro_no_socios", message=frappe.get_traceback())
