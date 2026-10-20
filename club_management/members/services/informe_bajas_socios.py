"""Informe «Bajas de socios» por rango de fechas (spec informe_bajas_socios.md)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)

ESTADO_BAJA = "Baja"
_TOLERANCIA = 0.005
_ROLES_INFORME = frozenset({"Secretaria", "System Manager"})


def _require_report_access() -> None:
	if not _ROLES_INFORME.intersection(frappe.get_roles()):
		frappe.throw(_("No tiene permiso para este informe."), frappe.PermissionError)


def _normalizar(filters: dict[str, Any] | None) -> frappe._dict:
	f = frappe._dict(filters or {})
	if not f.get("fecha_desde") or not f.get("fecha_hasta"):
		frappe.throw(_("Indicá fecha desde y fecha hasta."), frappe.ValidationError)
	f.fecha_desde = getdate(f.fecha_desde)
	f.fecha_hasta = getdate(f.fecha_hasta)
	if f.fecha_hasta < f.fecha_desde:
		frappe.throw(
			_("La fecha hasta debe ser posterior o igual a la fecha desde."),
			frappe.ValidationError,
		)
	return f


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
			"label": _("Apellido"),
			"fieldname": "apellido",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Nombre"),
			"fieldname": "nombre",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Fecha de baja"),
			"fieldname": "fecha_baja",
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"label": _("Actividades"),
			"fieldname": "actividades",
			"fieldtype": "Data",
			"width": 260,
		},
		{
			"label": _("Deuda pendiente"),
			"fieldname": "tiene_deuda_pendiente",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Saldo deuda"),
			"fieldname": "saldo_deuda",
			"fieldtype": "Currency",
			"width": 130,
		},
	]


def _actividades_por_socio(socio_names: list[str]) -> dict[str, list[str]]:
	if not socio_names:
		return {}
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"socio": ["in", socio_names]},
		fields=["socio", "actividad"],
		order_by="creation asc, name asc",
	)
	out: dict[str, list[str]] = {}
	for row in rows:
		actividad = (row.actividad or "").strip()
		if not actividad:
			continue
		lista = out.setdefault(row.socio, [])
		if actividad not in lista:
			lista.append(actividad)
	return out


def _saldos_desde_facturas(socio_names: list[str]) -> dict[str, float] | None:
	if not socio_names or not erpnext_cobranza_disponible():
		return None
	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo:
		return None
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo: ["in", socio_names],
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=[campo, "outstanding_amount"],
	)
	out = {name: 0.0 for name in socio_names}
	for row in rows:
		socio = row.get(campo)
		if socio in out:
			out[socio] = flt(out[socio] + flt(row.outstanding_amount), 2)
	return out


def get_bajas_socios(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	"""Filas del informe de socios en Baja dentro del rango."""
	_require_report_access()
	f = _normalizar(filters)
	candidatos = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": ESTADO_BAJA},
		fields=["name", "nombre", "apellido", "fecha_baja", "ultimo_cambio_estado_en", "saldo_deuda"],
		order_by="apellido asc, nombre asc",
	)
	rows = []
	for row in candidatos:
		fecha = getdate(row.fecha_baja) if row.fecha_baja else getdate(row.ultimo_cambio_estado_en)
		if not fecha or fecha < f.fecha_desde or fecha > f.fecha_hasta:
			continue
		row.fecha_baja_efectiva = fecha
		rows.append(row)
	rows.sort(key=lambda row: (row.apellido or "", row.nombre or ""))
	rows.sort(key=lambda row: row.fecha_baja_efectiva, reverse=True)
	if not rows:
		return []

	actividades = _actividades_por_socio([row.name for row in rows])
	if f.get("actividad"):
		rows = [row for row in rows if f.actividad in actividades.get(row.name, [])]
		if not rows:
			return []

	saldos_factura = _saldos_desde_facturas([row.name for row in rows])
	result: list[dict[str, Any]] = []
	for row in rows:
		if saldos_factura is None:
			saldo = flt(row.saldo_deuda)
		else:
			saldo = flt(saldos_factura.get(row.name, 0))
		tiene_deuda = saldo > _TOLERANCIA
		if f.get("tiene_deuda") == "Con deuda" and not tiene_deuda:
			continue
		if f.get("tiene_deuda") == "Sin deuda" and tiene_deuda:
			continue
		result.append(
			{
				"nro_socio": row.name,
				"apellido": row.apellido or "",
				"nombre": row.nombre or "",
				"fecha_baja": row.fecha_baja_efectiva,
				"actividades": ", ".join(actividades.get(row.name, [])),
				"tiene_deuda_pendiente": _("Sí") if tiene_deuda else _("No"),
				"saldo_deuda": saldo,
			}
		)
	return result


def get_bajas_socios_report(
	filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
	return get_report_columns(), get_bajas_socios(filters)
