"""Controller del DocType `Socio`.

Implementa las invariantes mínimas del Sprint 0 documentadas en
`club_management/specs/socio_minimo.md`:

- `estado` no es editable directamente desde el formulario; cualquier cambio
  debe pasar por `members.services.socio_transitions.cambiar_estado`, que
  configura el flag `flags.estado_change_authorized` antes de guardar.
- `fecha_alta` se setea la primera vez que `estado` pasa a `"Activo"` y no
  vuelve a modificarse.
- Cuando `categoria = "Menor"`, exige `tipo_tutor`, `tutor` y `grupo_familiar`
  consistentes: el tutor debe ser mayor de 18 y figurar como titular activo en
  el grupo declarado.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


ESTADOS_BLOQUEADOS_MANUALMENTE = {"Vitalicio"}


class Socio(Document):
	def validate(self) -> None:
		self._validate_estado_solo_via_servicio()
		self._set_fecha_alta_si_corresponde()
		if self.categoria == "Menor":
			self._validate_menor()

	def _validate_estado_solo_via_servicio(self) -> None:
		if self.flags.get("estado_change_authorized"):
			return

		if self.is_new():
			if self.estado and self.estado in ESTADOS_BLOQUEADOS_MANUALMENTE:
				frappe.throw(
					_("El estado {0} no puede asignarse manualmente; se obtiene por proceso server-side.").format(
						self.estado
					)
				)
			return

		previous = self.get_doc_before_save()
		if not previous:
			return

		if self.estado != previous.estado:
			frappe.throw(
				_("El estado debe modificarse a través del servicio `cambiar_estado`, no editando el campo directamente.")
			)

	def _set_fecha_alta_si_corresponde(self) -> None:
		if self.estado == "Activo" and not self.fecha_alta:
			self.fecha_alta = today()

	def _validate_menor(self) -> None:
		faltantes = [
			campo
			for campo in ("tipo_tutor", "tutor", "grupo_familiar")
			if not self.get(campo)
		]
		if faltantes:
			frappe.throw(
				_("Socio menor requiere `tipo_tutor`, `tutor` y `grupo_familiar` (faltan: {0})").format(
					", ".join(faltantes)
				)
			)

		tutor_doctype = self.tipo_tutor
		tutor_name = self.tutor

		tutor_doc = frappe.get_doc(tutor_doctype, tutor_name)
		tutor_birth = getdate(tutor_doc.fecha_nacimiento)
		hoy = date.today()
		edad = hoy.year - tutor_birth.year - ((hoy.month, hoy.day) < (tutor_birth.month, tutor_birth.day))
		if edad < 18:
			frappe.throw(_("Tutor debe ser mayor de 18 años"))

		grupo = frappe.get_doc("Grupo Familiar", self.grupo_familiar)
		es_titular_activo = any(
			fila.tipo_titular == tutor_doctype
			and fila.titular == tutor_name
			and not fila.hasta
			for fila in (grupo.titulares or [])
		)
		if not es_titular_activo:
			frappe.throw(_("Tutor debe ser titular activo del Grupo Familiar del menor"))
