"""Equipo / categoría dentro de un grupo de actividad."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class EquipoActividad(Document):
	def before_insert(self) -> None:
		if not self.name:
			self.name = self._build_name()

	def validate(self) -> None:
		if not self.name:
			self.name = self._build_name()
		self._validate_unique_en_grupo()

	def _build_name(self) -> str:
		return f"{self.grupo_actividad} / {self.titulo}".strip()

	def _validate_unique_en_grupo(self) -> None:
		filters: dict = {"grupo_actividad": self.grupo_actividad, "titulo": self.titulo}
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		if frappe.db.exists("Equipo Actividad", filters):
			frappe.throw(
				_("Ya existe el equipo {0} en el grupo {1}.").format(
					self.titulo, self.grupo_actividad
				)
			)
