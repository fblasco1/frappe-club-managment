"""Payload del dashboard Desk de Espacios (pendientes + agenda del día)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe.utils import getdate, today

from club_management.spaces.availability import dia_semana_de_fecha, get_occupancy
from club_management.spaces.planilla import sort_espacios_planilla


def _fmt_hora(value: Any) -> str:
	text = str(value or "")
	if len(text) >= 5:
		return text[:5]
	return text


def list_reservas_pendientes() -> list[dict[str, Any]]:
	"""Solicitudes de reserva en estado Pendiente."""
	return frappe.get_all(
		"Reserva Espacio",
		filters={"estado": "Pendiente"},
		fields=[
			"name",
			"espacio",
			"fecha",
			"hora_desde",
			"hora_hasta",
			"tipo",
			"motivo",
			"socio",
			"arrendatario_nombre",
		],
		order_by="fecha asc, hora_desde asc",
	)


def list_actividades_del_dia(
	*,
	fecha: str | date | None = None,
	espacio: str | None = None,
) -> list[dict[str, Any]]:
	"""Agenda del día (grilla + reservas que ocupan), ordenada por hora."""
	ref = getdate(fecha or today())
	filters: dict[str, Any] = {"habilitado": 1}
	if espacio:
		filters["name"] = espacio
	espacios = sort_espacios_planilla(
		frappe.get_all("Espacio", filters=filters, fields=["name", "titulo", "tipo"])
	)

	items: list[dict[str, Any]] = []
	for esp in espacios:
		for raw in get_occupancy(esp["name"], ref):
			titulo = (
				raw.get("titulo")
				or raw.get("motivo")
				or raw.get("tipo_sesion")
				or raw.get("tipo")
				or raw.get("name")
				or ""
			)
			items.append(
				{
					"espacio": esp["name"],
					"espacio_titulo": esp.get("titulo") or esp["name"],
					"hora_desde": _fmt_hora(raw.get("hora_desde")),
					"hora_hasta": _fmt_hora(raw.get("hora_hasta")),
					"titulo": str(titulo),
					"source": raw.get("source"),
					"tipo": raw.get("tipo") or raw.get("tipo_sesion"),
					"ref": raw.get("name") or raw.get("row_name"),
				}
			)

	items.sort(key=lambda row: (row.get("hora_desde") or "", row.get("espacio") or ""))
	return items


def list_espacios_selector() -> list[dict[str, Any]]:
	return sort_espacios_planilla(
		frappe.get_all(
			"Espacio",
			filters={"habilitado": 1},
			fields=["name", "titulo", "tipo"],
		)
	)


def get_espacios_desk_dashboard_payload(
	*,
	fecha: str | date | None = None,
	espacio: str | None = None,
) -> dict[str, Any]:
	ref = getdate(fecha or today())
	return {
		"fecha": str(ref),
		"dia_semana": dia_semana_de_fecha(ref),
		"pendientes": list_reservas_pendientes(),
		"actividades_dia": list_actividades_del_dia(fecha=ref, espacio=espacio or None),
		"espacios": list_espacios_selector(),
		"espacio_filtro": espacio or "",
	}
