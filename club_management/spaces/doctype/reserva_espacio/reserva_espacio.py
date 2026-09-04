"""DocType Reserva Espacio: ocupación puntual o alquiler externo (temp/recurrente)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from club_management.spaces.availability import (
	assert_no_overlap_with_occupancy,
	assert_no_overlap_with_reservations_only,
	assert_recurring_no_overlap,
	iter_recurrence_dates,
	validate_time_range,
)
from club_management.spaces.fixtures.superposicion import refresh_superposicion_flag

TIPOS_VALIDOS = frozenset({"Alquiler externo", "Alquiler socio", "Evento club", "Bloqueo"})
ESTADOS_QUE_OCUPAN = frozenset({"Confirmada"})
MODALIDADES_ALQUILER = frozenset({"Temporal", "Recurrente"})


class ReservaEspacio(Document):
	def validate(self) -> None:
		validate_time_range(self.hora_desde, self.hora_hasta)
		if self.tipo and self.tipo not in TIPOS_VALIDOS:
			frappe.throw(
				_("Tipo de reserva no permitido: {0}").format(self.tipo),
				frappe.ValidationError,
			)

		if self.tipo == "Alquiler externo":
			self._validate_alquiler_externo()
		elif self.tipo == "Evento club" and self.recurrencia_semanal:
			self._validate_evento_club_recurrente()
		else:
			self.modalidad_alquiler = None
			self.recurrencia_semanal = 0
			self.fecha_desde = None
			self.fecha_hasta = None
			self.set("dias_recurrencia", [])
			if not self.fecha:
				frappe.throw(_("La fecha es obligatoria"), frappe.ValidationError)

		if self.estado in ESTADOS_QUE_OCUPAN and self.espacio:
			self._assert_occupancy()

	def _is_fixture_import(self) -> bool:
		return bool((self.origen_fixture or "").strip())

	def _validate_alquiler_externo(self) -> None:
		alquilable = frappe.db.get_value("Espacio", self.espacio, "alquilable")
		if not alquilable:
			frappe.throw(
				_("El espacio debe ser alquilable para Alquiler externo"),
				frappe.ValidationError,
			)
		modalidad = (self.modalidad_alquiler or "").strip()
		if modalidad not in MODALIDADES_ALQUILER:
			frappe.throw(
				_("Modalidad de alquiler obligatoria: Temporal o Recurrente"),
				frappe.ValidationError,
			)
		if not (self.arrendatario_nombre or "").strip():
			frappe.throw(
				_("Indicá el nombre del arrendatario externo"),
				frappe.ValidationError,
			)

		if modalidad == "Temporal":
			if not self.fecha:
				frappe.throw(_("La fecha es obligatoria para alquiler Temporal"), frappe.ValidationError)
			self.fecha_desde = None
			self.fecha_hasta = None
			self.set("dias_recurrencia", [])
		else:
			if not self.fecha_desde or not self.fecha_hasta:
				frappe.throw(
					_("Fecha desde y hasta son obligatorias para alquiler Recurrente"),
					frappe.ValidationError,
				)
			if getdate(self.fecha_hasta) < getdate(self.fecha_desde):
				frappe.throw(
					_("fecha_hasta debe ser mayor o igual a fecha_desde"),
					frappe.ValidationError,
				)
			dias = {row.dia_semana for row in (self.get("dias_recurrencia") or []) if row.dia_semana}
			if not dias:
				frappe.throw(
					_("Indicá al menos un día de la semana para el alquiler Recurrente"),
					frappe.ValidationError,
				)
			if not self.fecha:
				self.fecha = self.fecha_desde

	def _validate_evento_club_recurrente(self) -> None:
		self.modalidad_alquiler = None
		if not self.fecha_desde or not self.fecha_hasta:
			frappe.throw(
				_("Fecha desde y hasta son obligatorias para Evento club recurrente"),
				frappe.ValidationError,
			)
		if getdate(self.fecha_hasta) < getdate(self.fecha_desde):
			frappe.throw(
				_("fecha_hasta debe ser mayor o igual a fecha_desde"),
				frappe.ValidationError,
			)
		dias = {row.dia_semana for row in (self.get("dias_recurrencia") or []) if row.dia_semana}
		if not dias:
			frappe.throw(
				_("Indicá al menos un día de la semana para el evento recurrente"),
				frappe.ValidationError,
			)
		if not self.fecha:
			self.fecha = self.fecha_desde

	def _is_recurring_reserva(self) -> bool:
		if self.tipo == "Alquiler externo" and (self.modalidad_alquiler or "").strip() == "Recurrente":
			return True
		return bool(self.tipo == "Evento club" and self.recurrencia_semanal)

	def _assert_occupancy(self) -> None:
		exclude = None if self.is_new() else self.name
		if self._is_fixture_import():
			refresh_superposicion_flag(self)
			return
		if self._is_recurring_reserva():
			dias = {row.dia_semana for row in (self.get("dias_recurrencia") or []) if row.dia_semana}
			if getattr(self.flags, "skip_grid_overlap_check", False):
				for occ in iter_recurrence_dates(
					self.fecha_desde, self.fecha_hasta, dias
				):
					assert_no_overlap_with_reservations_only(
						self.espacio,
						occ,
						self.hora_desde,
						self.hora_hasta,
						exclude_reserva=exclude,
					)
				return
			assert_recurring_no_overlap(
				self.espacio,
				self.fecha_desde,
				self.fecha_hasta,
				dias,
				self.hora_desde,
				self.hora_hasta,
				exclude_reserva=exclude,
			)
			return
		if not self.fecha:
			frappe.throw(_("La fecha es obligatoria"), frappe.ValidationError)
		if getattr(self.flags, "skip_grid_overlap_check", False):
			assert_no_overlap_with_reservations_only(
				self.espacio,
				self.fecha,
				self.hora_desde,
				self.hora_hasta,
				exclude_reserva=exclude,
			)
			return
		assert_no_overlap_with_occupancy(
			self.espacio,
			self.fecha,
			self.hora_desde,
			self.hora_hasta,
			exclude_reserva=exclude,
		)
