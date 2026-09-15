"""Patch idempotente: default Club Settings para reserva externa online."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	if not frappe.get_meta("Club Settings").has_field("espacios_reserva_externa_habilitada"):
		return
	current = frappe.db.get_single_value(
		"Club Settings", "espacios_reserva_externa_habilitada"
	)
	# Solo setear default 0 si aún no hay valor explícito (None / ausente).
	if current is None:
		frappe.db.set_single_value(
			"Club Settings",
			"espacios_reserva_externa_habilitada",
			0,
			update_modified=False,
		)
