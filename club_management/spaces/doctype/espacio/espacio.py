"""DocType Espacio: lugar físico con grilla semanal."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from club_management.spaces.availability import (
	TIPOS_SESION,
	assert_grid_compatible_with_confirmed_reservations,
	assert_horarios_table_valid_ranges,
	build_horario_titulo,
	validate_activity_links,
)


class Espacio(Document):
	def validate(self) -> None:
		horarios = list(self.get("horarios") or [])
		assert_horarios_table_valid_ranges(horarios)
		for row in horarios:
			tipo = (row.tipo_sesion or "").strip()
			if not tipo:
				frappe.throw(_("Tipo de sesión es obligatorio en cada horario"), frappe.ValidationError)
			if tipo not in TIPOS_SESION:
				frappe.throw(
					_("Tipo de sesión no válido: {0}").format(tipo),
					frappe.ValidationError,
				)
			validate_activity_links(row.actividad, row.grupo_actividad, row.equipo_actividad)
			row.titulo = build_horario_titulo(
				row.actividad,
				row.grupo_actividad,
				row.equipo_actividad,
				tipo_sesion=tipo,
				etiqueta=getattr(row, "etiqueta", None),
			)
		if self.name and not self.is_new():
			if not getattr(self.flags, "skip_spaces_grid_reserva_check", False):
				assert_grid_compatible_with_confirmed_reservations(self.name, horarios)
