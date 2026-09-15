"""API Desk — descarga PDF de ocupación de espacios."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.desk.utils import provide_binary_file

from club_management.spaces.permissions import ensure_spaces_read_access
from club_management.spaces.services.ocupacion_reporte_pdf import (
	build_ocupacion_reporte_pdf_bytes,
	reporte_pdf_filename,
)


@frappe.whitelist()
def download_ocupacion_pdf(
	fecha: str | None = None,
	fecha_desde: str | None = None,
	fecha_hasta: str | None = None,
	fechas: str | list | None = None,
) -> None:
	"""Descarga PDF de la planilla de ocupación (08:00–04:00) para fecha(s)."""
	ensure_spaces_read_access()
	if not frappe.has_permission("Espacio", "read"):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)

	kwargs: dict[str, Any] = {
		"fecha": fecha,
		"fecha_desde": fecha_desde,
		"fecha_hasta": fecha_hasta,
		"fechas": fechas,
	}
	content = build_ocupacion_reporte_pdf_bytes(**kwargs)
	stem = reporte_pdf_filename(**kwargs)
	provide_binary_file(stem, "pdf", content)
