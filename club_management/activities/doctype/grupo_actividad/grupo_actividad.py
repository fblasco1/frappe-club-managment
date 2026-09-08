"""Grupo / tira dentro de una actividad (arancel por grupo)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class GrupoActividad(Document):
	def before_insert(self) -> None:
		if not self.name:
			self.name = self._build_name()

	def validate(self) -> None:
		if not self.name:
			self.name = self._build_name()
		self._validate_unique_en_actividad()

	def _build_name(self) -> str:
		return f"{self.actividad} / {self.titulo}".strip()

	def _validate_unique_en_actividad(self) -> None:
		filters: dict = {"actividad": self.actividad, "titulo": self.titulo}
		if not self.is_new():
			filters["name"] = ["!=", self.name]
		if frappe.db.exists("Grupo Actividad", filters):
			frappe.throw(
				_("Ya existe el grupo {0} en la actividad {1}.").format(
					self.titulo, self.actividad
				)
			)
