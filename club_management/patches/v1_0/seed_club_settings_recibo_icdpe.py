"""Datos de recibo térmico ICDPE en Club Settings."""

from __future__ import annotations

import frappe

_RECIBO_ICDPE = {
	"recibo_institucion_nombre": "Institucion Cultural y Deportiva Pedro Echague",
	"recibo_institucion_direccion": "PORTELA 836 - CABA",
	"recibo_cuit": "30-59845346-9",
	"recibo_condicion_iva": "IVA EXENTO",
	"recibo_mensaje_pie": "SOMOS ECHAGUE, SOMOS FAMILIA !!",
	"recibo_ancho_papel_mm": "58",
}


def execute() -> None:
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	settings = frappe.get_single("Club Settings")
	for fieldname, value in _RECIBO_ICDPE.items():
		if frappe.get_meta("Club Settings").has_field(fieldname):
			settings.set(fieldname, value)
	settings.save(ignore_permissions=True)
