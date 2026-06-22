"""Consulta y liquidación manual de deuda por equipo / rango de fechas.

Spec: `club_management/specs/liquidacion_equipo_deuda_rango.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.activities.services.inscripcion_socio import INSCRIPCION_DOCTYPE
from club_management.members.doctype.socio.socio import format_socio_nombre_completo
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)

PERIODO_COBRANZA_FIELDS = ("periodo_cobro", "custom_periodo_cobro")
ENTRENADOR_LIQUIDACION_RATIO = 0.8


def validar_filtros_liquidacion(filters: dict[str, Any] | frappe._dict) -> None:
	"""Valida filtros comunes del reporte y las APIs de liquidación."""
	filters = frappe._dict(filters or {})
	fecha_desde = filters.get("fecha_desde")
	fecha_hasta = filters.get("fecha_hasta")
	if not fecha_desde or not fecha_hasta:
		frappe.throw(_("Indique fecha desde y fecha hasta."), frappe.ValidationError)

	desde = getdate(fecha_desde)
	hasta = getdate(fecha_hasta)
	if hasta < desde:
		frappe.throw(_("La fecha hasta debe ser posterior o igual a la fecha desde."), frappe.ValidationError)

	if not any(filters.get(key) for key in ("actividad", "grupo_actividad", "equipo_actividad")):
		frappe.throw(
			_("Debe elegir al menos una actividad, grupo o equipo."),
			frappe.ValidationError,
		)


def build_inscripcion_filters(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	validar_filtros_liquidacion(filters)
	filters = frappe._dict(filters)
	ins_filters: dict[str, Any] = {"estado": "Activa"}
	if filters.get("equipo_actividad"):
		ins_filters["equipo_actividad"] = filters.equipo_actividad
	if filters.get("grupo_actividad"):
		ins_filters["grupo_actividad"] = filters.grupo_actividad
	if filters.get("actividad"):
		ins_filters["actividad"] = filters.actividad
	return ins_filters


def _campo_periodo_cobro() -> str | None:
	for fieldname in PERIODO_COBRANZA_FIELDS:
		if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field(fieldname):
			return fieldname
	return None


def _factura_filters_socio(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
	*,
	solo_pendientes: bool = True,
) -> dict[str, Any]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	filters: dict[str, Any] = {
		campo_socio: socio_name,
		"docstatus": 1,
		"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
	}
	if solo_pendientes:
		filters["outstanding_amount"] = [">", 0]
	return filters


def get_facturas_pendientes_socio_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> list[dict[str, Any]]:
	"""Facturas pendientes del socio con posting_date en el rango."""
	if not erpnext_cobranza_disponible():
		return []

	campo_periodo = _campo_periodo_cobro()
	fields = ["name", "posting_date", "due_date", "outstanding_amount", "grand_total"]
	if campo_periodo:
		fields.append(campo_periodo)

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=_factura_filters_socio(socio_name, fecha_desde, fecha_hasta),
		fields=fields,
		order_by="posting_date asc, name asc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		result.append(
			{
				"name": row.name,
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"outstanding_amount": flt(row.outstanding_amount),
				"grand_total": flt(row.grand_total),
				"periodo_cobro": row.get(campo_periodo) if campo_periodo else None,
			}
		)
	return result


def calcular_deuda_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> tuple[float, int]:
	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	total = sum(flt(row["outstanding_amount"]) for row in facturas)
	return total, len(facturas)


def calcular_saldo_total_socio(socio_name: str) -> float:
	return sync_saldo_deuda_socio(socio_name)


def _inscripciones_por_socio(filters: dict[str, Any] | frappe._dict) -> dict[str, dict[str, Any]]:
	ins_filters = build_inscripcion_filters(filters)
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=ins_filters,
		fields=[
			"name",
			"socio",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
		],
		order_by="modified desc",
	)
	by_socio: dict[str, dict[str, Any]] = {}
	for row in rows:
		if row.socio not in by_socio:
			by_socio[row.socio] = row
	return by_socio


def get_deuda_por_equipo_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Deuda por equipo»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de deuda requiere ERPNext (Sales Invoice)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	validar_filtros_liquidacion(filters)
	inscripciones = _inscripciones_por_socio(filters)
	if not inscripciones:
		return []

	socio_names = list(inscripciones.keys())
	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "estado": ["!=", "Baja"]},
		fields=["name", "nombre", "apellido", "estado"],
	)
	socio_by_name = {row.name: row for row in socios}

	rows: list[dict[str, Any]] = []
	for socio_name, ins in inscripciones.items():
		socio = socio_by_name.get(socio_name)
		if not socio:
			continue

		deuda_en_rango, cantidad = calcular_deuda_en_rango(
			socio_name,
			str(filters.fecha_desde),
			str(filters.fecha_hasta),
		)
		if not int(filters.get("incluir_saldo_cero") or 0) and deuda_en_rango <= 0:
			continue

		nombre_apellido = format_socio_nombre_completo(socio.apellido, socio.nombre) or socio_name

		rows.append(
			{
				"socio": socio_name,
				"nombre_apellido": nombre_apellido,
				"estado": socio.estado,
				"actividad": ins.actividad,
				"grupo_actividad": ins.grupo_actividad or "",
				"equipo_actividad": ins.equipo_actividad or "",
				"deuda_en_rango": deuda_en_rango,
				"saldo_total": calcular_saldo_total_socio(socio_name),
				"cantidad_facturas": cantidad,
			}
		)

	rows.sort(key=lambda row: (-flt(row["deuda_en_rango"]), row["nombre_apellido"].lower()))
	return rows


def calcular_pagos_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> tuple[float, int]:
	"""Suma importe cobrado de facturas del socio emitidas en el rango."""
	if not erpnext_cobranza_disponible():
		return 0.0, 0

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return 0.0, 0

	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
		},
		fields=["grand_total", "outstanding_amount"],
	)
	paid_rows = [
		row
		for row in invoices
		if flt(row.grand_total) - flt(row.outstanding_amount) > 0
	]
	total = sum(flt(row.grand_total) - flt(row.outstanding_amount) for row in paid_rows)
	return total, len(paid_rows)


def get_pagos_por_equipo_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Pagos por equipo»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de pagos requiere ERPNext (Payment Entry)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	validar_filtros_liquidacion(filters)
	inscripciones = _inscripciones_por_socio(filters)
	if not inscripciones:
		return []

	socio_names = list(inscripciones.keys())
	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "estado": ["!=", "Baja"]},
		fields=["name", "nombre", "apellido", "estado"],
	)
	socio_by_name = {row.name: row for row in socios}

	rows: list[dict[str, Any]] = []
	for socio_name, ins in inscripciones.items():
		socio = socio_by_name.get(socio_name)
		if not socio:
			continue

		pagos_en_rango, cantidad = calcular_pagos_en_rango(
			socio_name,
			str(filters.fecha_desde),
			str(filters.fecha_hasta),
		)
		if not int(filters.get("incluir_saldo_cero") or 0) and pagos_en_rango <= 0:
			continue

		nombre_apellido = format_socio_nombre_completo(socio.apellido, socio.nombre) or socio_name
		liquidacion_entrenador = flt(pagos_en_rango) * ENTRENADOR_LIQUIDACION_RATIO

		rows.append(
			{
				"socio": socio_name,
				"nombre_apellido": nombre_apellido,
				"estado": socio.estado,
				"actividad": ins.actividad,
				"grupo_actividad": ins.grupo_actividad or "",
				"equipo_actividad": ins.equipo_actividad or "",
				"pagos_en_rango": pagos_en_rango,
				"liquidacion_entrenador": liquidacion_entrenador,
				"cantidad_pagos": cantidad,
			}
		)

	rows.sort(key=lambda row: (-flt(row["pagos_en_rango"]), row["nombre_apellido"].lower()))
	return rows


def get_pagos_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 140},
		{"label": _("Apellido, nombre/s"), "fieldname": "nombre_apellido", "fieldtype": "Data", "width": 200},
		{"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 110},
		{"label": _("Actividad"), "fieldname": "actividad", "fieldtype": "Link", "options": "Actividad", "width": 140},
		{
			"label": _("Grupo / tira"),
			"fieldname": "grupo_actividad",
			"fieldtype": "Link",
			"options": "Grupo Actividad",
			"width": 140,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_actividad",
			"fieldtype": "Link",
			"options": "Equipo Actividad",
			"width": 140,
		},
		{
			"label": _("Pagos en rango"),
			"fieldname": "pagos_en_rango",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Liquidación entrenador (80%)"),
			"fieldname": "liquidacion_entrenador",
			"fieldtype": "Currency",
			"width": 170,
		},
		{
			"label": _("Cantidad de pagos"),
			"fieldname": "cantidad_pagos",
			"fieldtype": "Int",
			"width": 120,
		},
	]


def get_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 140},
		{"label": _("Apellido, nombre/s"), "fieldname": "nombre_apellido", "fieldtype": "Data", "width": 200},
		{"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 110},
		{"label": _("Actividad"), "fieldname": "actividad", "fieldtype": "Link", "options": "Actividad", "width": 140},
		{
			"label": _("Grupo / tira"),
			"fieldname": "grupo_actividad",
			"fieldtype": "Link",
			"options": "Grupo Actividad",
			"width": 140,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_actividad",
			"fieldtype": "Link",
			"options": "Equipo Actividad",
			"width": 140,
		},
		{
			"label": _("Deuda en rango"),
			"fieldname": "deuda_en_rango",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Saldo total"), "fieldname": "saldo_total", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Facturas pendientes"),
			"fieldname": "cantidad_facturas",
			"fieldtype": "Int",
			"width": 120,
		},
	]


def assert_factura_liquidable_en_rango(
	socio_name: str,
	sales_invoice_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> None:
	"""Valida socio, rango y saldo pendiente antes de registrar cobro."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice_name)
	if campo_socio and invoice.get(campo_socio) != socio_name:
		frappe.throw(_("La factura no pertenece a este socio."), frappe.ValidationError)

	posting = getdate(invoice.posting_date)
	desde = getdate(fecha_desde)
	hasta = getdate(fecha_hasta)
	if posting < desde or posting > hasta:
		frappe.throw(_("La factura no pertenece al rango de fechas indicado."), frappe.ValidationError)

	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("La factura no tiene saldo pendiente."), frappe.ValidationError)


def registrar_cobro_liquidacion(
	socio_name: str,
	sales_invoice_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	assert_factura_liquidable_en_rango(socio_name, sales_invoice_name, fecha_desde, fecha_hasta)
	payment_entry = registrar_cobro_manual(socio_name, sales_invoice_name)
	saldo = sync_saldo_deuda_socio(socio_name)
	deuda_en_rango, _cantidad = calcular_deuda_en_rango(socio_name, fecha_desde, fecha_hasta)
	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	return {
		"payment_entry": payment_entry,
		"saldo_total": saldo,
		"deuda_en_rango": deuda_en_rango,
		"estado": estado,
	}


def liquidar_deuda_socio_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	payment_entries: list[str] = []
	for row in facturas:
		result = registrar_cobro_liquidacion(
			socio_name,
			row["name"],
			fecha_desde,
			fecha_hasta,
		)
		payment_entries.append(result["payment_entry"])

	saldo = sync_saldo_deuda_socio(socio_name)
	deuda_en_rango, cantidad = calcular_deuda_en_rango(socio_name, fecha_desde, fecha_hasta)
	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	return {
		"payment_entries": payment_entries,
		"saldo_total": saldo,
		"deuda_en_rango": deuda_en_rango,
		"cantidad_facturas": cantidad,
		"estado": estado,
	}


def default_report_filters() -> dict[str, str | int]:
	first_day = getdate(today()).replace(day=1)
	return {
		"fecha_desde": str(first_day),
		"fecha_hasta": str(today()),
		"incluir_saldo_cero": 0,
	}
