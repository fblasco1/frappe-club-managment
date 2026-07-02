"""Búsqueda rápida de socios desde la navegación Desk del club."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint

SOCIO_DOCTYPE = "Socio"


def search_socios(*, query: str, limit: int = 8) -> list[dict[str, Any]]:
	text = (query or "").strip()
	if len(text) < 2:
		return []
	if not frappe.has_permission(SOCIO_DOCTYPE, "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		or_filters={
			"dni": ["like", f"%{text}%"],
			"apellido": ["like", f"%{text}%"],
			"nombre": ["like", f"%{text}%"],
			"nombre_completo": ["like", f"%{text}%"],
		},
		fields=["name", "dni", "nombre", "apellido", "numero_socio", "estado"],
		limit_page_length=cint(limit),
		order_by="apellido asc, nombre asc",
	)
	results = []
	for row in rows:
		label = f"{row.get('apellido') or ''}, {row.get('nombre') or ''}".strip(", ")
		if row.get("dni"):
			label = f"{label} — DNI {row['dni']}".strip()
		results.append(
			{
				"name": row["name"],
				"label": label or row["name"],
				"dni": row.get("dni"),
				"numero_socio": row.get("numero_socio"),
				"estado": row.get("estado"),
			}
		)
	return results
