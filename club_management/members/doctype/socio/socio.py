"""Controller del DocType `Socio`.

Implementa las invariantes mínimas del Sprint 0 documentadas en
`club_management/specs/socio_minimo.md`:

- `estado` no es editable directamente desde el formulario; cualquier cambio
  debe pasar por `members.services.socio_transitions.cambiar_estado`, que
  configura el flag `flags.estado_change_authorized` antes de guardar.
- `fecha_alta` se setea la primera vez que `estado` pasa a `"Activo"` y no
  vuelve a modificarse.
- Cuando `categoria = "Menor"`, exige `tipo_tutor` y `tutor` (adulto responsable).
  Si además tiene `grupo_familiar`, valida que el tutor sea titular activo del grupo.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Max
from frappe.utils import getdate, today


ESTADOS_BLOQUEADOS_MANUALMENTE = {"Vitalicio"}


def format_socio_nombre_completo(apellido: str | None, nombre: str | None) -> str:
	"""Etiqueta Desk: «Apellido, Nombre/s»."""
	ap = (apellido or "").strip()
	nom = (nombre or "").strip()
	if ap and nom:
		return f"{ap}, {nom}"
	return ap or nom or ""


class Socio(Document):
	def before_insert(self) -> None:
		"""Asigna el número de socio (PK) según la estrategia de naming.

		- **Migración histórica (alta manual desde el Desk):** si `numero_socio`
		  viene cargado, se respeta el número real del club.
		- **Alta nueva (validación de Solicitud vía web):** si `numero_socio` está
		  vacío, se calcula `MAX(numero_socio) + 1` (con respaldo en `name` numérico).

		Se ejecuta antes de `set_new_name`; con `autoname = "field:numero_socio"`
		Frappe deriva el `name` desde este campo. Se fija `self.name` explícitamente
		para dejar la invariante (PK == número de socio) clara y robusta.
		"""
		if self.numero_socio:
			self.numero_socio = int(self.numero_socio)
		else:
			self.numero_socio = self._siguiente_numero_socio()
		self.name = str(self.numero_socio)

	@staticmethod
	def _siguiente_numero_socio() -> int:
		"""Devuelve el siguiente número de socio para PostgreSQL v14.

		Prioriza ``MAX(numero_socio)`` (columna entera del DocType). Durante la
		migración desde series ``SOC-…``, filas legacy pueden tener
		``numero_socio = 0`` pero ``name`` ya numérico; en ese caso se usa
		``MAX(name::INTEGER)`` solo sobre nombres puramente numéricos.
		"""
		socio = frappe.qb.DocType("Socio")
		resultado = frappe.qb.from_(socio).select(Max(socio.numero_socio)).run()
		max_numero = int((resultado[0][0] if resultado and resultado[0] else 0) or 0)

		max_name = frappe.db.sql(
			"""
			SELECT MAX(name::INTEGER)
			FROM "tabSocio"
			WHERE name ~ '^[0-9]+$'
			"""
		)[0][0]
		max_name = int(max_name or 0)

		return max(max_numero, max_name) + 1

	def validate(self) -> None:
		self._validate_numero_socio_disponible()
		self._sync_nombre_completo()
		self._validate_estado_solo_via_servicio()
		self._set_fecha_alta_si_corresponde()
		if self.categoria == "Menor":
			self._validate_menor()

	def before_save(self) -> None:
		from club_management.members.services.datos_criticos_socio import aplicar_edicion_parcial_secretaria

		aplicar_edicion_parcial_secretaria(self)

	def _validate_numero_socio_disponible(self) -> None:
		if not self.is_new() or not self.numero_socio:
			return

		numero = int(self.numero_socio)
		if numero <= 0:
			frappe.throw(_("El número de socio debe ser un entero positivo."))

		if frappe.db.exists("Socio", str(numero)):
			frappe.throw(
				_("El número de socio {0} ya está asignado a otro socio.").format(numero),
				frappe.ValidationError,
			)

	def _sync_nombre_completo(self) -> None:
		self.nombre_completo = format_socio_nombre_completo(self.apellido, self.nombre)

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
		from club_management.members.services.datos_criticos_socio import usuario_puede_edicion_parcial_secretaria

		faltantes = [
			campo for campo in ("tipo_tutor", "tutor") if not self.get(campo)
		]
		if faltantes and not self.is_new() and usuario_puede_edicion_parcial_secretaria():
			return
		if faltantes:
			frappe.throw(
				_("Socio menor requiere tutor responsable (faltan: {0})").format(
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

		if not self.grupo_familiar:
			return

		grupo = frappe.get_doc("Grupo Familiar", self.grupo_familiar)
		es_titular_activo = any(
			fila.tipo_titular == tutor_doctype
			and fila.titular == tutor_name
			and not fila.hasta
			for fila in (grupo.titulares or [])
		)
		if not es_titular_activo:
			frappe.throw(_("Tutor debe ser titular activo del Grupo Familiar del menor"))
