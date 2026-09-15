"""Índice único parcial para slot de Reserva Espacio (espacio|fecha|horario)."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Reserva Espacio"):
		return
	frappe.db.sql(
		"""
		CREATE UNIQUE INDEX IF NOT EXISTS uq_reserva_espacio_slot_key
		ON "tabReserva Espacio" (slot_key)
		WHERE slot_key IS NOT NULL AND slot_key <> ''
		"""
	)
