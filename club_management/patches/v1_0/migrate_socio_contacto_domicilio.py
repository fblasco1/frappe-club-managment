"""Copia contacto/domicilio legacy de `Socio` y elimina columnas obsoletas."""

from __future__ import annotations

import frappe

_TABLE = "`tabSocio`"


def execute() -> None:
	if not frappe.db.table_exists("Socio"):
		return

	if frappe.db.has_column("Socio", "telefono") and frappe.db.has_column("Socio", "telefono_movil"):
		frappe.db.sql(
			f"""
			UPDATE {_TABLE}
			SET telefono_movil = COALESCE(NULLIF(TRIM(telefono_movil), ''), telefono)
			WHERE telefono IS NOT NULL AND TRIM(telefono) != ''
			"""
		)

	if frappe.db.has_column("Socio", "domicilio") and frappe.db.has_column("Socio", "calle"):
		frappe.db.sql(
			f"""
			UPDATE {_TABLE}
			SET calle = COALESCE(NULLIF(TRIM(calle), ''), domicilio)
			WHERE domicilio IS NOT NULL AND TRIM(domicilio) != ''
			"""
		)

	if frappe.db.has_column("Socio", "localidad") and frappe.db.has_column("Socio", "localidad_barrio"):
		frappe.db.sql(
			f"""
			UPDATE {_TABLE}
			SET localidad_barrio = COALESCE(NULLIF(TRIM(localidad_barrio), ''), localidad)
			WHERE localidad IS NOT NULL AND TRIM(localidad) != ''
			"""
		)

	for column in ("telefono", "domicilio", "localidad"):
		if frappe.db.has_column("Socio", column):
			frappe.db.sql_ddl(f"ALTER TABLE {_TABLE} DROP COLUMN `{column}`")
