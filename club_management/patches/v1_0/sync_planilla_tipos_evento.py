"""Renombra tipos de evento al catálogo operativo de la planilla."""

from __future__ import annotations

import frappe


def execute() -> None:
	frappe.db.sql(
		"""
		UPDATE `tabHorario Entrenamiento`
		SET tipo_sesion = 'Entrenamiento'
		WHERE tipo_sesion = 'Entrenamiento deportivo'
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabHorario Entrenamiento`
		SET tipo_sesion = 'Preparacion Fisica'
		WHERE tipo_sesion IN ('Preparación física', 'Preparacion fisica')
		"""
	)
	frappe.db.sql(
		"""
		UPDATE `tabReserva Espacio`
		SET tipo = 'Alquiler socio'
		WHERE tipo = 'Uso interno'
		"""
	)
