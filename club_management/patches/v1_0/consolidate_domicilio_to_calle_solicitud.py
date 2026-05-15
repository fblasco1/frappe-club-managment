"""Copia datos `domicilio*` → `calle*` y elimina columnas legacy si coexisten.

Tras `migrate`, el DocType ya puede haber creado `calle` mientras `domicilio`
seguía en la tabla; el patch `rename_domicilio_to_calle_solicitud` no corre en
ese caso. Este patch cierra la migración C2.5.
"""

from __future__ import annotations

import frappe


def execute() -> None:
	table = "`tabSolicitud Asociacion`"

	if frappe.db.has_column("Solicitud Asociacion", "domicilio") and frappe.db.has_column(
		"Solicitud Asociacion", "calle"
	):
		frappe.db.sql(
			f"""
			UPDATE {table}
			SET calle = COALESCE(NULLIF(TRIM(calle), ''), domicilio)
			WHERE domicilio IS NOT NULL AND TRIM(domicilio) != ''
			"""
		)
		frappe.db.sql_ddl(f"ALTER TABLE {table} DROP COLUMN `domicilio`")

	if frappe.db.has_column("Solicitud Asociacion", "domicilio_tutor") and frappe.db.has_column(
		"Solicitud Asociacion", "calle_tutor"
	):
		frappe.db.sql(
			f"""
			UPDATE {table}
			SET calle_tutor = COALESCE(NULLIF(TRIM(calle_tutor), ''), domicilio_tutor)
			WHERE domicilio_tutor IS NOT NULL AND TRIM(domicilio_tutor) != ''
			"""
		)
		frappe.db.sql_ddl(f"ALTER TABLE {table} DROP COLUMN `domicilio_tutor`")
