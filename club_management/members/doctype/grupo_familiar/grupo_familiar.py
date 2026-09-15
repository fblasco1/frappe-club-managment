"""Controller del DocType `Grupo Familiar`.

Implementa las invariantes mínimas del Sprint 0 documentadas en
`club_management/specs/grupo_familiar_minimo.md`:

- Al menos un titular activo y **exactamente uno** marcado como principal.
- Todos los titulares activos son mayores de 18.
- `(tipo_titular, titular)` único entre filas activas dentro del grupo.
- `(tipo_titular, titular)` único entre todos los grupos activos del sistema.
- Sincronización idempotente: cada titular activo con `tipo_titular = "Socio"`
  aparece en `miembros` con `rol = "Titular"` y `hasta` vacío.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now, today


class GrupoFamiliar(Document):
	def validate(self) -> None:
		self._validate_titulares_no_vacio()
		self._validate_unico_principal_activo()
		self._validate_sin_duplicados_de_titular_en_grupo()
		self._validate_titulares_mayores_de_edad()
		self._validate_titularidad_unica_cross_grupo()
		self._sync_socios_titulares_como_miembros()

	def before_insert(self) -> None:
		self.creado_por = frappe.session.user
		self.creado_en = now()
		self.ultima_modificacion_por = frappe.session.user
		self.ultima_modificacion_en = now()

	def before_save(self) -> None:
		if not self.is_new():
			self.ultima_modificacion_por = frappe.session.user
			self.ultima_modificacion_en = now()

	def get_titular_principal(self) -> tuple[str, str] | None:
		for fila in self._titulares_activos():
			if fila.es_principal:
				return (fila.tipo_titular, fila.titular)
		return None

	def _titulares_activos(self):
		return [fila for fila in (self.titulares or []) if not fila.hasta]

	def _validate_titulares_no_vacio(self) -> None:
		if not self._titulares_activos():
			frappe.throw(_("El Grupo Familiar debe tener al menos un titular activo"))

	def _validate_unico_principal_activo(self) -> None:
		principales = [fila for fila in self._titulares_activos() if fila.es_principal]
		if len(principales) != 1:
			frappe.throw(_("Debe haber exactamente un titular principal activo"))

	def _validate_sin_duplicados_de_titular_en_grupo(self) -> None:
		vistos: set[tuple[str, str]] = set()
		for fila in self._titulares_activos():
			clave = (fila.tipo_titular, fila.titular)
			if clave in vistos:
				frappe.throw(
					_("Titular duplicado dentro del grupo: {0} / {1}").format(*clave)
				)
			vistos.add(clave)

	def _validate_titulares_mayores_de_edad(self) -> None:
		hoy = date.today()
		for fila in self._titulares_activos():
			persona = frappe.get_doc(fila.tipo_titular, fila.titular)
			fecha_nac = getdate(persona.fecha_nacimiento)
			edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
			if edad < 18:
				frappe.throw(_("Titular debe ser mayor de 18 años"))

	def _validate_titularidad_unica_cross_grupo(self) -> None:
		for fila in self._titulares_activos():
			conflictos = frappe.db.sql(
				"""
				SELECT t.parent
				FROM `tabTitular de Grupo Familiar` t
				WHERE t.parenttype = 'Grupo Familiar'
				  AND t.tipo_titular = %(tipo)s
				  AND t.titular = %(titular)s
				  AND t.hasta IS NULL
				  AND t.parent != %(self_name)s
				""",
				{
					"tipo": fila.tipo_titular,
					"titular": fila.titular,
					"self_name": self.name or "",
				},
			)
			if conflictos:
				frappe.throw(
					_("La persona ya es titular activa en otro Grupo Familiar ({0})").format(
						conflictos[0][0]
					)
				)

	def _sync_socios_titulares_como_miembros(self) -> None:
		if self.miembros is None:
			self.miembros = []

		miembros_activos = {
			fila.socio: fila
			for fila in self.miembros
			if not fila.hasta
		}

		for titular in self._titulares_activos():
			if titular.tipo_titular != "Socio":
				continue
			if titular.titular in miembros_activos:
				continue
			self.append(
				"miembros",
				{
					"socio": titular.titular,
					"rol": "Titular",
					"desde": today(),
				},
			)
