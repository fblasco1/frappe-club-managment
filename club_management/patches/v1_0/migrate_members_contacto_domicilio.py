"""Migra contacto/domicilio legacy en `Tutor No Socio` y `Solicitud Asociacion`."""

from __future__ import annotations

import frappe

_TNS = "`tabTutor No Socio`"
_SOL = "`tabSolicitud Asociacion`"


def execute() -> None:
	_migrate_tutor_no_socio()
	_migrate_solicitud_asociacion()


def _migrate_tutor_no_socio() -> None:
	if not frappe.db.table_exists("Tutor No Socio"):
		return

	if frappe.db.has_column("Tutor No Socio", "telefono") and frappe.db.has_column(
		"Tutor No Socio", "telefono_movil"
	):
		frappe.db.sql(
			f"""
			UPDATE {_TNS}
			SET telefono_movil = COALESCE(NULLIF(TRIM(telefono_movil), ''), telefono)
			WHERE telefono IS NOT NULL AND TRIM(telefono) != ''
			"""
		)

	if frappe.db.has_column("Tutor No Socio", "domicilio") and frappe.db.has_column(
		"Tutor No Socio", "calle"
	):
		frappe.db.sql(
			f"""
			UPDATE {_TNS}
			SET calle = COALESCE(NULLIF(TRIM(calle), ''), domicilio)
			WHERE domicilio IS NOT NULL AND TRIM(domicilio) != ''
			"""
		)

	if frappe.db.has_column("Tutor No Socio", "localidad") and frappe.db.has_column(
		"Tutor No Socio", "localidad_barrio"
	):
		frappe.db.sql(
			f"""
			UPDATE {_TNS}
			SET localidad_barrio = COALESCE(NULLIF(TRIM(localidad_barrio), ''), localidad)
			WHERE localidad IS NOT NULL AND TRIM(localidad) != ''
			"""
		)

	for column in ("telefono", "domicilio", "localidad"):
		if frappe.db.has_column("Tutor No Socio", column):
			frappe.db.sql_ddl(f"ALTER TABLE {_TNS} DROP COLUMN `{column}`")


def _migrate_solicitud_asociacion() -> None:
	if not frappe.db.table_exists("Solicitud Asociacion"):
		return

	_copy_solicitud_legacy("telefono", "telefono_movil")
	_copy_solicitud_legacy("localidad", "localidad_barrio")
	_copy_solicitud_legacy("telefono_tutor", "telefono_movil_tutor")
	_copy_solicitud_legacy("localidad_tutor", "localidad_barrio_tutor")

	for column in ("telefono", "localidad", "telefono_tutor", "localidad_tutor"):
		if frappe.db.has_column("Solicitud Asociacion", column):
			frappe.db.sql_ddl(f"ALTER TABLE {_SOL} DROP COLUMN `{column}`")


def _copy_solicitud_legacy(source: str, target: str) -> None:
	if not frappe.db.has_column("Solicitud Asociacion", source):
		return
	if not frappe.db.has_column("Solicitud Asociacion", target):
		return
	frappe.db.sql(
		f"""
		UPDATE {_SOL}
		SET {target} = COALESCE(NULLIF(TRIM({target}), ''), {source})
		WHERE {source} IS NOT NULL AND TRIM({source}) != ''
		"""
	)
