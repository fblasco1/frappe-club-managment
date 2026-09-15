"""Asegura unicidad idempotente de fixtures en PostgreSQL."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Reserva Espacio"):
		return
	frappe.db.sql(
		"""
		CREATE UNIQUE INDEX IF NOT EXISTS
			"idx_reserva_espacio_fixture_unique"
		ON "tabReserva Espacio" ("origen_fixture", "id_externo_fixture")
		WHERE COALESCE("origen_fixture", '') <> ''
		  AND COALESCE("id_externo_fixture", '') <> ''
		"""
	)
