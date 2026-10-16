"""Default densidad de impresión del recibo térmico = Máxima."""

from __future__ import annotations

import frappe


def execute() -> None:
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	if not frappe.get_meta("Club Settings").has_field("recibo_densidad_impresion"):
		return
	settings = frappe.get_single("Club Settings")
	actual = (settings.recibo_densidad_impresion or "").strip()
	if actual:
		return
	settings.recibo_densidad_impresion = "Máxima"
	settings.save(ignore_permissions=True)
