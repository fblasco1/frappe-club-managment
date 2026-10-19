"""Datos del Script Report «Inscriptos por Actividad» (spec reporte_inscriptos_actividad.md)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE
from club_management.members.doctype.socio.socio import format_socio_nombre_completo

SOCIO_DOCTYPE = "Socio"
EQUIPO_DOCTYPE = "Equipo Actividad"


def _require_report_access() -> None:
	roles = set(frappe.get_roles())
	if not roles.intersection({"System Manager", "Secretaria"}):
		frappe.throw(_("No tiene permiso para este informe."), frappe.PermissionError)


def get_report_columns() -> list[dict[str, Any]]:
	return [
		{
			"label": _("Nro. socio"),
			"fieldname": "nro_socio",
			"fieldtype": "Link",
			"options": SOCIO_DOCTYPE,
			"width": 100,
		},
		{
			"label": _("Nombre"),
			"fieldname": "nombre",
			"fieldtype": "Data",
			"width": 220,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_categoria",
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"label": _("Estado"),
			"fieldname": "estado",
			"fieldtype": "Data",
			"width": 90,
		},
	]


def _etiqueta_equipo_categoria(
	*,
	equipo: str | None,
	grupo: str | None,
	actividad: str | None,
) -> str:
	if equipo:
		return equipo
	if grupo:
		return grupo
	return (actividad or "").strip()


@frappe.whitelist()
@frappe.read_only()
def equipo_actividad_query(
	doctype: str,
	txt: str,
	searchfield: str,
	start: int,
	page_len: int,
	filters: dict[str, Any] | str | None = None,
) -> list[list[str]]:
	"""Link query: equipos de la actividad (y opcionalmente del grupo)."""
	_require_report_access()
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = filters or {}
	actividad = (filters.get("actividad") or "").strip()
	grupo = (filters.get("grupo_actividad") or "").strip()
	txt = (txt or "").strip()
	conds = ['ea."habilitada" = 1']
	values: dict[str, Any] = {
		"txt": f"%{txt}%",
		"start": cint(start),
		"page_len": cint(page_len) or 20,
	}
	if grupo:
		conds.append("ea.grupo_actividad = %(grupo)s")
		values["grupo"] = grupo
	elif actividad:
		conds.append("ga.actividad = %(actividad)s")
		values["actividad"] = actividad
	else:
		return []
	if txt:
		conds.append("(ea.name ILIKE %(txt)s OR COALESCE(ea.titulo, '') ILIKE %(txt)s)")
	where = " AND ".join(conds)
	return frappe.db.sql(
		f"""
		SELECT ea.name, COALESCE(ea.titulo, ea.name)
		FROM "tabEquipo Actividad" ea
		INNER JOIN "tabGrupo Actividad" ga ON ga.name = ea.grupo_actividad
		WHERE {where}
		ORDER BY ea.name
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		values,
	)


def get_inscriptos_por_actividad_data(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	"""Filas del reporte: nombre legible + ruta equipo (sin columnas actividad/grupo)."""
	_require_report_access()
	filters = filters or {}
	actividad = (filters.get("actividad") or "").strip()
	if not actividad:
		return []
	ins_filters: dict[str, Any] = {"actividad": actividad}
	estado = (filters.get("estado") or "Activa").strip()
	if estado:
		ins_filters["estado"] = estado
	grupo = (filters.get("grupo_actividad") or "").strip()
	if grupo:
		ins_filters["grupo_actividad"] = grupo
	equipo = (filters.get("equipo_actividad") or "").strip()
	if equipo:
		ins_filters["equipo_actividad"] = equipo

	inscripciones = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=ins_filters,
		fields=["socio", "actividad", "grupo_actividad", "equipo_actividad", "estado"],
		order_by="actividad asc, grupo_actividad asc, equipo_actividad asc, socio asc",
	)
	if not inscripciones:
		return []

	socio_names = sorted({row.socio for row in inscripciones if row.socio})
	socios = {
		row.name: row
		for row in frappe.get_all(
			SOCIO_DOCTYPE,
			filters={"name": ["in", socio_names]},
			fields=["name", "nombre", "apellido", "nombre_completo"],
		)
	}

	rows: list[dict[str, Any]] = []
	for ins in inscripciones:
		socio = socios.get(ins.socio)
		if socio:
			nombre = (socio.nombre_completo or "").strip() or format_socio_nombre_completo(
				socio.apellido, socio.nombre
			)
		else:
			nombre = ""
		rows.append(
			{
				"nro_socio": ins.socio,
				"nombre": nombre,
				"equipo_categoria": _etiqueta_equipo_categoria(
					equipo=ins.equipo_actividad,
					grupo=ins.grupo_actividad,
					actividad=ins.actividad,
				),
				"estado": ins.estado,
			}
		)
	rows.sort(key=lambda r: ((r.get("nombre") or "").lower(), str(r.get("nro_socio") or "")))
	return rows
