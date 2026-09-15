"""Mover auditoría de validación de `Socio` a `Solicitud de Asociación`.

Sprint 0 agregó `alta_validada_por` y `alta_validada_en` a `Socio` anticipando
que el flujo de validación de Sprint 1 las poblara. Sprint 1 cambia la decisión
(I1 c en `specs/solicitud_asociacion_publica.md`): la auditoría de la
validación vive exclusivamente en `Solicitud de Asociación` (`validado_por` /
`validado_en`). El `Socio` se vincula vía `solicitud_origen`.

Este patch dropea las columnas del schema. No hay riesgo de pérdida de datos:
los campos están vacíos en producción (ningún código los poblaba en Sprint 0).
"""

from __future__ import annotations

import frappe


_COLUMNS_TO_DROP: tuple[str, ...] = ("alta_validada_por", "alta_validada_en")


def execute() -> None:
	existing: set[str] = set(frappe.db.get_table_columns("Socio"))
	for col in _COLUMNS_TO_DROP:
		if col in existing:
			frappe.db.sql_ddl(f"ALTER TABLE `tabSocio` DROP COLUMN `{col}`")
