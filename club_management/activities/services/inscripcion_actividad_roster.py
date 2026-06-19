"""Listado de socios inscriptos por grupo/equipo (formulario Inscripcion Actividad)."""

from __future__ import annotations

from typing import Any

import frappe

from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE, SOCIO_DOCTYPE
from club_management.members.services.cobranza_manual import get_ultima_fecha_pago_socio


def list_socios_inscripcion_grupo_equipo(
	*,
	grupo_actividad: str | None = None,
	equipo_actividad: str | None = None,
) -> list[dict[str, Any]]:
	"""Socios con inscripción activa en el equipo (prioridad) o en el grupo."""
	grupo_actividad = (grupo_actividad or "").strip() or None
	equipo_actividad = (equipo_actividad or "").strip() or None

	if equipo_actividad:
		ins_filters: dict[str, Any] = {"estado": "Activa", "equipo_actividad": equipo_actividad}
	elif grupo_actividad:
		ins_filters = {"estado": "Activa", "grupo_actividad": grupo_actividad}
	else:
		return []

	socio_names = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=ins_filters,
		pluck="socio",
		distinct=True,
	)
	if not socio_names:
		return []

	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "estado": ["!=", "Baja"]},
		fields=["name", "nombre", "apellido", "dni", "telefono_movil"],
		order_by="apellido asc, nombre asc, name asc",
	)

	rows: list[dict[str, Any]] = []
	for socio in socios:
		ult_fecha_pago = get_ultima_fecha_pago_socio(socio.name)
		rows.append(
			{
				"socio": socio.name,
				"nombre": socio.nombre,
				"apellido": socio.apellido,
				"dni": socio.dni,
				"telefono_movil": socio.telefono_movil or "",
				"ult_fecha_pago": ult_fecha_pago,
			}
		)
	return rows
