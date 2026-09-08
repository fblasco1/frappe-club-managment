"""Alinea Club Settings: 2.º vencimiento operativo = día 20."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	settings = frappe.get_single("Club Settings")
	current = (settings.dia_segundo_vencimiento or "").strip()
	# Solo fuerza el default operativo si aún está en fin de mes o vacío.
	if current in ("", "Ultimo dia del mes"):
		settings.dia_segundo_vencimiento = "20"
		settings.save(ignore_permissions=True)
