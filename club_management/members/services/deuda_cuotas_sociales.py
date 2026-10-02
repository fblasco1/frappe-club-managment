"""Informe «Deuda cuotas sociales»: cuota social impaga por socio (spec deuda_cuotas_sociales.md)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
)
from club_management.members.services.liquidacion_equipo import _cuota_social_item_codes
from club_management.members.services.mora_al_cobro import parse_periodo_cobro
from club_management.scripts.informe_concepto_cobranza import _cobros_imputados_por_linea

ESTADO_BAJA = "Baja"
_TOLERANCIA = 0.005


def get_columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "socio", "label": _("Socio"), "fieldtype": "Link", "options": "Socio", "width": 110},
		{"fieldname": "nombre", "label": _("Apellido y nombre"), "fieldtype": "Data", "width": 220},
		{"fieldname": "categoria", "label": _("Categoría"), "fieldtype": "Data", "width": 120},
		{"fieldname": "estado", "label": _("Estado"), "fieldtype": "Data", "width": 90},
		{"fieldname": "telefono", "label": _("Teléfono"), "fieldtype": "Data", "width": 120},
		{"fieldname": "periodos", "label": _("Períodos adeudados"), "fieldtype": "Data", "width": 260},
		{"fieldname": "cantidad_periodos", "label": _("Cant."), "fieldtype": "Int", "width": 70},
		{"fieldname": "deuda", "label": _("Deuda cuota social"), "fieldtype": "Currency", "width": 140},
	]


def _periodo_key(periodo: str | None) -> date:
	return parse_periodo_cobro(periodo) or date.min


def _filtro_periodo(filters: dict[str, Any], key: str) -> date | None:
	raw = (filters.get(key) or "").strip()
	if not raw:
		return None
	parsed = parse_periodo_cobro(raw)
	if not parsed:
		frappe.throw(_("Período inválido «{0}»: usá el formato MM/AAAA.").format(raw))
	return parsed


def _lineas_cuota_impagas(filters: dict[str, Any]) -> list[dict[str, Any]]:
	codes = sorted(_cuota_social_item_codes())
	if not codes:
		return []
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	conditions = [
		"si.docstatus = 1",
		"si.is_return = 0",
		"si.outstanding_amount > 0",
		"sii.item_code in %(codes)s",
	]
	params: dict[str, Any] = {"codes": tuple(codes)}
	if filters.get("categoria"):
		conditions.append("s.categoria = %(categoria)s")
		params["categoria"] = filters["categoria"]
	if filters.get("estado"):
		conditions.append("s.estado = %(estado)s")
		params["estado"] = filters["estado"]
	else:
		conditions.append("coalesce(s.estado, '') != %(baja)s")
		params["baja"] = ESTADO_BAJA
	if filters.get("socio"):
		conditions.append("s.name = %(socio)s")
		params["socio"] = filters["socio"]

	return frappe.db.sql(
		f"""
		select
			si.name as invoice,
			si.{campo_periodo} as periodo,
			si.grand_total,
			si.outstanding_amount,
			sii.item_code,
			sii.amount,
			s.name as socio,
			s.nombre_completo,
			s.apellido,
			s.nombre,
			s.categoria,
			s.estado,
			s.telefono_movil
		from "tab{SALES_INVOICE_DOCTYPE} Item" sii
		join "tab{SALES_INVOICE_DOCTYPE}" si on si.name = sii.parent
		join "tabSocio" s on s.name = si.{campo_socio}
		where {" and ".join(conditions)}
		order by s.name, si.name, sii.idx
		""",
		params,
		as_dict=True,
	)


def _restante_cuota_por_factura(lineas: list[dict[str, Any]]) -> dict[str, float]:
	"""Cuota social impaga por factura; si hubo cobros parciales, imputa por línea."""
	codes = _cuota_social_item_codes()
	por_factura: dict[str, float] = {}
	parciales: set[str] = set()
	for row in lineas:
		if flt(row.outstanding_amount) + _TOLERANCIA < flt(row.grand_total):
			parciales.add(row.invoice)
			continue
		por_factura[row.invoice] = flt(por_factura.get(row.invoice, 0) + flt(row.amount), 2)
	for invoice in parciales:
		restante = sum(
			flt(r.get("restante"), 2)
			for r in _cobros_imputados_por_linea(invoice)
			if r.get("item_code") in codes
		)
		por_factura[invoice] = flt(restante, 2)
	return por_factura


def get_deuda_cuotas_sociales_rows(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	filters = frappe._dict(filters or {})
	desde = _filtro_periodo(filters, "periodo_desde")
	hasta = _filtro_periodo(filters, "periodo_hasta")

	lineas = _lineas_cuota_impagas(filters)
	if desde or hasta:
		lineas = [
			row
			for row in lineas
			if parse_periodo_cobro(row.periodo)
			and (not desde or parse_periodo_cobro(row.periodo) >= desde)
			and (not hasta or parse_periodo_cobro(row.periodo) <= hasta)
		]
	restante = _restante_cuota_por_factura(lineas)

	socios: dict[str, dict[str, Any]] = {}
	facturas_vistas: set[str] = set()
	for row in lineas:
		if row.invoice in facturas_vistas:
			continue
		facturas_vistas.add(row.invoice)
		monto = flt(restante.get(row.invoice), 2)
		if monto <= _TOLERANCIA:
			continue
		entry = socios.setdefault(
			row.socio,
			{
				"socio": row.socio,
				"nombre": row.nombre_completo or " ".join(p for p in (row.apellido, row.nombre) if p),
				"categoria": row.categoria,
				"estado": row.estado,
				"telefono": row.telefono_movil,
				"_periodos": set(),
				"deuda": 0.0,
			},
		)
		entry["_periodos"].add(row.periodo or "")
		entry["deuda"] = flt(entry["deuda"] + monto, 2)

	data: list[dict[str, Any]] = []
	for entry in socios.values():
		periodos = sorted(entry.pop("_periodos"), key=_periodo_key)
		entry["periodos"] = ", ".join(p or _("(sin período)") for p in periodos)
		entry["cantidad_periodos"] = len(periodos)
		data.append(entry)
	data.sort(key=lambda r: (-r["cantidad_periodos"], -r["deuda"], r["nombre"] or ""))
	return data


def get_report_summary(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
	total = flt(sum(flt(r["deuda"]) for r in data), 2)
	return [
		{"label": _("Socios con deuda"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Períodos adeudados"),
			"value": sum(int(r["cantidad_periodos"]) for r in data),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{"label": _("Total adeudado"), "value": total, "datatype": "Currency", "indicator": "Red"},
	]


def get_deuda_cuotas_sociales(
	filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], None, None, list[dict[str, Any]]]:
	data = get_deuda_cuotas_sociales_rows(filters)
	return get_columns(), data, None, None, get_report_summary(data)
