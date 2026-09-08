"""Inscripción de un socio a una actividad (con grupo/tira y equipo opcional)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class InscripcionActividad(Document):
	def validate(self) -> None:
		self._validate_actividad_grupo_equipo()
		self._validate_unica_activa()

	def _validate_actividad_grupo_equipo(self) -> None:
		usa_grupos = frappe.db.get_value("Actividad", self.actividad, "usa_grupos")
		if usa_grupos and not self.grupo_actividad:
			frappe.throw(
				_("La actividad {0} requiere elegir un grupo / tira.").format(self.actividad)
			)
		if self.grupo_actividad:
			grupo_actividad = frappe.db.get_value(
				"Grupo Actividad", self.grupo_actividad, "actividad"
			)
			if grupo_actividad != self.actividad:
				frappe.throw(_("El grupo no pertenece a la actividad seleccionada."))
		if self.equipo_actividad:
			if not self.grupo_actividad:
				frappe.throw(_("Debe indicar el grupo / tira antes del equipo."))
			grupo_equipo = frappe.db.get_value(
				"Equipo Actividad", self.equipo_actividad, "grupo_actividad"
			)
			if grupo_equipo != self.grupo_actividad:
				frappe.throw(_("El equipo no pertenece al grupo / tira seleccionado."))
		if not usa_grupos and (self.grupo_actividad or self.equipo_actividad):
			frappe.throw(
				_("La actividad {0} no utiliza grupos; quite grupo y equipo.").format(
					self.actividad
				)
			)

	def _validate_unica_activa(self) -> None:
		if self.estado != "Activa":
			return
		filters: dict = {"socio": self.socio, "estado": "Activa"}
		if self.grupo_actividad:
			filters["grupo_actividad"] = self.grupo_actividad
			if self.equipo_actividad:
				filters["equipo_actividad"] = self.equipo_actividad
		else:
			filters["actividad"] = self.actividad
			filters["grupo_actividad"] = ["is", "not set"]
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		if frappe.db.exists("Inscripcion Actividad", filters):
			frappe.throw(_("Ya existe una inscripción activa equivalente para este socio."))
