"""Migra estado `Rechazada` a `Requiere Corrección` (Sprint 1 cierre).

- Elimina el estado terminal Rechazada del flujo: toda observación vuelve como
  corrección solicitada.
- Si `motivos_rechazo` tiene contenido y `observaciones_secretaria` está vacío,
  copia el texto a `observaciones_secretaria`.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	cols = set(frappe.db.get_table_columns("Solicitud Asociacion"))
	if "workflow_state" not in cols:
		return

	# Copiar motivos a observaciones si aplica.
	if "motivos_rechazo" in cols and "observaciones_secretaria" in cols:
		frappe.db.sql(
			"""
			update `tabSolicitud Asociacion`
			set observaciones_secretaria = motivos_rechazo
			where workflow_state = 'Rechazada'
			  and coalesce(trim(motivos_rechazo), '') != ''
			  and coalesce(trim(observaciones_secretaria), '') = ''
			"""
		)

	# Migrar estado.
	frappe.db.sql(
		"""
		update `tabSolicitud Asociacion`
		set workflow_state = 'Requiere Corrección'
		where workflow_state = 'Rechazada'
		"""
	)

