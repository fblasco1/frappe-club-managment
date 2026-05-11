"""Controller del DocType `Tutor No Socio`.

Implementa las invariantes mínimas del Sprint 0 documentadas en
`club_management/specs/tutor_no_socio_minimo.md`:

- `fecha_nacimiento` corresponde a una persona mayor de 18 años.
- Auditoría de creación y última modificación.

Las validaciones de unicidad de `dni` y `user` son delegadas a Frappe (campos
`unique=1` en el JSON).
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now


class TutorNoSocio(Document):
	def validate(self) -> None:
		self._validate_mayor_de_edad()

	def before_insert(self) -> None:
		self.creado_por = frappe.session.user
		self.creado_en = now()
		self.ultima_modificacion_por = frappe.session.user
		self.ultima_modificacion_en = now()

	def before_save(self) -> None:
		if not self.is_new():
			self.ultima_modificacion_por = frappe.session.user
			self.ultima_modificacion_en = now()

	def _validate_mayor_de_edad(self) -> None:
		if not self.fecha_nacimiento:
			return
		fecha = getdate(self.fecha_nacimiento)
		today = date.today()
		edad = today.year - fecha.year - ((today.month, today.day) < (fecha.month, fecha.day))
		if edad < 18:
			frappe.throw(_("Tutor No Socio debe ser mayor de 18 años"))
