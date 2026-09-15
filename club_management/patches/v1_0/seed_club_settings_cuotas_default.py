"""Cuotas sociales por defecto en Club Settings (MVP sin pagos)."""

from __future__ import annotations

import frappe

_CUOTAS_DEFAULT: tuple[tuple[str, float], ...] = (
	("Activo", 15000.0),
	("Menor", 12000.0),
	("Adherente", 10000.0),
	("Jubilado", 8000.0),
)


def execute() -> None:
	if not frappe.db.exists("DocType", "Club Settings"):
		return
	settings = frappe.get_single("Club Settings")
	if not settings.company:
		company = frappe.db.get_value("Company", {}, "name")
		if company:
			settings.company = company
	existing = {row.categoria for row in (settings.cuotas_categoria or [])}
	for categoria, monto in _CUOTAS_DEFAULT:
		if categoria in existing:
			continue
		settings.append("cuotas_categoria", {"categoria": categoria, "monto": monto})
	settings.save(ignore_permissions=True)
