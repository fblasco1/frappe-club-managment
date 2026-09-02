"""Informe de recaudación imputada por concepto del informe de cobranza.

Spec: `club_management/specs/informe_rendicion_cobranza_secretaria.md` (fase 2)
"""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)
from club_management.members.services.concepto_informe_label import (
	agrupacion_tipo_concepto,
	etiqueta_concepto_informe_desde_linea_si,
)
from club_management.members.services.modos_pago_desk import DESK_MODOS_PAGO_COBRANZA
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)
from club_management.scripts.informe_concepto_cobranza import concepto_informe_desde_pe

_AGRUPACIONES_VALIDAS = frozenset({"Cuota", "Arancel", "CTO COMP", "Federativa", "Otro"})
VISTA_RENDICION = "Rendición por concepto"
VISTA_PAGOS_DIA = "Pagos del día"


def _label_medio(mode: str) -> str:
	for row in DESK_MODOS_PAGO_COBRANZA:
		if row["value"] == mode:
			return _(row["label"])
	return mode


def _fold_sort_key(value: str | None) -> str:
	text = unicodedata.normalize("NFKD", value or "")
	return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _parse_filters(filters: dict[str, Any] | None) -> dict[str, Any]:
	raw = filters or {}
	fecha_desde = getdate(raw.get("fecha_desde") or today())
	fecha_hasta = getdate(raw.get("fecha_hasta") or today())
	if fecha_hasta < fecha_desde:
		fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
	agrupacion = (raw.get("agrupacion") or "").strip()
	if agrupacion and agrupacion not in _AGRUPACIONES_VALIDAS:
		agrupacion = ""
	return {
		"fecha_desde": fecha_desde,
		"fecha_hasta": fecha_hasta,
		"periodo_cobro": (raw.get("periodo_cobro") or "").strip(),
		"agrupacion": agrupacion,
		"solo_cuotas_sociales": bool(raw.get("solo_cuotas_sociales")),
		"medio_pago": (raw.get("medio_pago") or "").strip(),
	}


def _empty_informe(fecha_desde: date, fecha_hasta: date) -> dict[str, Any]:
	return {
		"fecha_desde": str(fecha_desde),
		"fecha_hasta": str(fecha_hasta),
		"lineas": [],
		"por_concepto": [],
		"por_medio": [],
		"total": 0.0,
	}


def _linea_pasa_filtros(
	concepto: str,
	*,
	agrupacion: str,
	solo_cuotas_sociales: bool,
) -> bool:
	if solo_cuotas_sociales and agrupacion_tipo_concepto(concepto) != "Cuota":
		return False
	if agrupacion and agrupacion_tipo_concepto(concepto) != agrupacion:
		return False
	return True


def get_informe_recaudacion_por_concepto(filters: dict[str, Any] | None = None) -> dict[str, Any]:
	"""Recaudación imputada en un rango, con etiquetas del informe manual."""
	ensure_secretaria_operacion_access()
	parsed = _parse_filters(filters)
	fecha_desde = parsed["fecha_desde"]
	fecha_hasta = parsed["fecha_hasta"]
	if not erpnext_cobranza_disponible():
		return _empty_informe(fecha_desde, fecha_hasta)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()

	pe_filters: dict[str, Any] = {
		"docstatus": 1,
		"payment_type": "Receive",
		"posting_date": ["between", [fecha_desde, fecha_hasta]],
	}
	if parsed["medio_pago"]:
		pe_filters["mode_of_payment"] = parsed["medio_pago"]

	pe_rows = frappe.get_all(
		"Payment Entry",
		filters=pe_filters,
		fields=[
			"name",
			"posting_date",
			"mode_of_payment",
			"paid_amount",
			"received_amount",
			"reference_no",
			"remarks",
		],
		order_by="posting_date asc, creation asc",
	)
	if not pe_rows:
		return _empty_informe(fecha_desde, fecha_hasta)

	pe_names = [row.name for row in pe_rows]
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"parent": ["in", pe_names],
			"parenttype": "Payment Entry",
			"reference_doctype": SALES_INVOICE_DOCTYPE,
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	refs_by_pe: dict[str, list[Any]] = {}
	invoice_names: set[str] = set()
	for ref in refs:
		refs_by_pe.setdefault(ref.parent, []).append(ref)
		invoice_names.add(ref.reference_name)

	if not invoice_names:
		return _empty_informe(fecha_desde, fecha_hasta)

	invoice_fields = ["name", "customer"]
	if campo_socio:
		invoice_fields.append(campo_socio)
	if campo_periodo:
		invoice_fields.append(campo_periodo)

	invoice_meta: dict[str, dict[str, Any]] = {}
	for inv in frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"name": ["in", list(invoice_names)]},
		fields=invoice_fields,
	):
		if parsed["periodo_cobro"] and campo_periodo:
			if (inv.get(campo_periodo) or "").strip() != parsed["periodo_cobro"]:
				continue
		invoice_meta[inv.name] = inv

	if not invoice_meta:
		return _empty_informe(fecha_desde, fecha_hasta)

	lineas_by_inv: dict[str, list[dict[str, Any]]] = {}
	for row in frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", list(invoice_meta)]},
		fields=["parent", "item_code", "description", "amount"],
		order_by="idx asc",
	):
		lineas_by_inv.setdefault(row.parent, []).append(row)

	socio_ids = {
		invoice_meta[name].get(campo_socio)
		for name in invoice_meta
		if campo_socio and invoice_meta.get(name, {}).get(campo_socio)
	}
	socio_names: dict[str, dict[str, Any]] = {}
	if socio_ids:
		socio_fields = ["name", "nombre", "apellido", "categoria"]
		meta = frappe.get_meta("Socio")
		if meta.has_field("numero_socio"):
			socio_fields.append("numero_socio")
		if meta.has_field("nro_socio_padron"):
			socio_fields.append("nro_socio_padron")
		for s in frappe.get_all(
			"Socio",
			filters={"name": ["in", list(socio_ids)]},
			fields=socio_fields,
		):
			socio_names[s.name] = s

	lineas: list[dict[str, Any]] = []
	por_concepto: dict[str, float] = {}
	por_medio: dict[str, float] = {}
	total = 0.0
	pe_by_name = {row.name: row for row in pe_rows}

	def _add_concepto(concepto: str, amount: float) -> None:
		por_concepto[concepto] = por_concepto.get(concepto, 0.0) + flt(amount)

	for pe_name, ref_rows in refs_by_pe.items():
		pe = pe_by_name.get(pe_name)
		if not pe:
			continue
		mode = pe.mode_of_payment or _("Sin medio")

		for ref in ref_rows:
			if ref.reference_name not in invoice_meta:
				continue
			allocated = flt(ref.allocated_amount)
			if allocated <= 0:
				continue

			inv = invoice_meta[ref.reference_name]
			inv_socio = inv.get(campo_socio) if campo_socio else None
			socio = socio_names.get(inv_socio or "") or {}
			apellido = (socio.get("apellido") or "").strip()
			nombre = (socio.get("nombre") or "").strip()
			label = f"{apellido}, {nombre}".strip(", ") or (inv_socio or "")
			periodo = (inv.get(campo_periodo) or "").strip() if campo_periodo else ""
			nro_socio = socio.get("numero_socio") or socio.get("nro_socio_padron") or ""
			categoria = socio.get("categoria")

			inv_lineas = lineas_by_inv.get(ref.reference_name) or []

			def _append(concepto: str, amount: float) -> None:
				if not _linea_pasa_filtros(
					concepto,
					agrupacion=parsed["agrupacion"],
					solo_cuotas_sociales=parsed["solo_cuotas_sociales"],
				):
					return
				nonlocal total
				amount_f = flt(amount)
				total += amount_f
				por_medio[mode] = por_medio.get(mode, 0.0) + amount_f
				_add_concepto(concepto, amount_f)
				lineas.append(
					{
						"concepto_informe": concepto,
						"posting_date": pe.posting_date,
						"socio": inv_socio,
						"nro_socio": str(nro_socio) if nro_socio is not None else "",
						"socio_label": label,
						"apellido": apellido,
						"nombre": nombre,
						"periodo": periodo,
						"mode_of_payment": mode,
						"paid_amount": amount_f,
						"payment_entry": pe_name,
						"sales_invoice": ref.reference_name,
					}
				)

			concepto_pe = concepto_informe_desde_pe(pe.reference_no, getattr(pe, "remarks", None))
			if concepto_pe:
				_append(concepto_pe, allocated)
				continue

			line_total = sum(flt(line.amount) for line in inv_lineas)

			if not inv_lineas or line_total <= 0:
				concepto = _("Sin concepto")
				_append(concepto, allocated)
				continue

			if len(inv_lineas) == 1:
				line = inv_lineas[0]
				concepto = etiqueta_concepto_informe_desde_linea_si(
					line.item_code,
					line.description,
					categoria_socio=categoria,
				)
				_append(concepto, allocated)
				continue

			acumulado = 0.0
			for idx, line in enumerate(inv_lineas):
				if idx == len(inv_lineas) - 1:
					parte = flt(allocated - acumulado)
				else:
					parte = flt(allocated * (flt(line.amount) / line_total))
					acumulado += parte
				concepto = etiqueta_concepto_informe_desde_linea_si(
					line.item_code,
					line.description,
					categoria_socio=categoria,
				)
				_append(concepto, parte)

	lineas.sort(
		key=lambda row: (
			_fold_sort_key(row.get("concepto_informe")),
			_fold_sort_key(row.get("apellido")),
			_fold_sort_key(row.get("nombre")),
			str(row.get("payment_entry") or ""),
		)
	)

	def _concepto_sort_key(name: str) -> tuple[int, str]:
		if agrupacion_tipo_concepto(name) == "Cuota":
			return (0, _fold_sort_key(name))
		return (1, _fold_sort_key(name))

	return {
		"fecha_desde": str(fecha_desde),
		"fecha_hasta": str(fecha_hasta),
		"lineas": lineas,
		"por_concepto": [
			{"concepto": k, "total": flt(v)}
			for k, v in sorted(por_concepto.items(), key=lambda item: _concepto_sort_key(item[0]))
		],
		"por_medio": [
			{"mode_of_payment": k, "total": flt(v)} for k, v in sorted(por_medio.items())
		],
		"total": flt(total),
	}


def get_recaudacion_por_concepto_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Concepto"), "fieldname": "concepto_informe", "fieldtype": "Data", "width": 200},
		{"label": _("Fecha cobro"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Nº socio"), "fieldname": "nro_socio", "fieldtype": "Data", "width": 90},
		{"label": _("Socio"), "fieldname": "socio_label", "fieldtype": "Data", "width": 180},
		{"label": _("Período"), "fieldname": "periodo", "fieldtype": "Data", "width": 80},
		{"label": _("Medio"), "fieldname": "mode_of_payment", "fieldtype": "Data", "width": 120},
		{"label": _("Monto"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{
			"label": _("Payment Entry"),
			"fieldname": "payment_entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 140,
		},
	]


def get_recaudacion_por_concepto_report_data(
	filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	informe = get_informe_recaudacion_por_concepto(filters)
	rows: list[dict[str, Any]] = []
	for linea in informe["lineas"]:
		rows.append(
			{
				"concepto_informe": linea.get("concepto_informe"),
				"posting_date": linea.get("posting_date"),
				"nro_socio": linea.get("nro_socio"),
				"socio_label": linea.get("socio_label"),
				"periodo": linea.get("periodo"),
				"mode_of_payment": _label_medio(str(linea.get("mode_of_payment") or "")),
				"paid_amount": linea.get("paid_amount"),
				"payment_entry": linea.get("payment_entry"),
			}
		)

	if informe["por_concepto"]:
		rows.append(
			{
				"concepto_informe": _("— Totales por concepto —"),
				"posting_date": None,
				"nro_socio": "",
				"socio_label": "",
				"periodo": "",
				"mode_of_payment": "",
				"paid_amount": None,
				"payment_entry": "",
			}
		)
		for row in informe["por_concepto"]:
			rows.append(
				{
					"concepto_informe": _("Total {0}").format(row["concepto"]),
					"posting_date": None,
					"nro_socio": "",
					"socio_label": "",
					"periodo": "",
					"mode_of_payment": "",
					"paid_amount": row["total"],
					"payment_entry": "",
				}
			)
	return rows


def get_recaudacion_por_concepto_report_summary(
	filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	informe = get_informe_recaudacion_por_concepto(filters)
	summary: list[dict[str, Any]] = [
		{"value": informe["total"], "label": _("Total recaudado"), "datatype": "Currency"},
	]
	for row in informe["por_medio"]:
		summary.append(
			{
				"value": row["total"],
				"label": _label_medio(row["mode_of_payment"]),
				"datatype": "Currency",
			}
		)
	return summary


def _is_pagos_dia_vista(filters: dict[str, Any] | None) -> bool:
	return (filters or {}).get("vista") == VISTA_PAGOS_DIA


def _filters_for_pagos_dia(filters: dict[str, Any] | None) -> dict[str, Any]:
	raw = filters or {}
	fecha = raw.get("fecha") or raw.get("fecha_desde") or today()
	return {"fecha": fecha}


def get_recaudacion_unificada_report_columns(
	filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	if _is_pagos_dia_vista(filters):
		from club_management.members.services.informe_pagos_del_dia import (
			get_pagos_del_dia_report_columns,
		)

		return get_pagos_del_dia_report_columns()
	return get_recaudacion_por_concepto_report_columns()


def get_recaudacion_unificada_report_data(
	filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	if _is_pagos_dia_vista(filters):
		from club_management.members.services.informe_pagos_del_dia import (
			get_pagos_del_dia_report_data,
		)

		return get_pagos_del_dia_report_data(_filters_for_pagos_dia(filters))
	return get_recaudacion_por_concepto_report_data(filters)


def get_recaudacion_unificada_report_summary(
	filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	if _is_pagos_dia_vista(filters):
		from club_management.members.services.informe_pagos_del_dia import (
			get_pagos_del_dia_report_summary,
		)

		return get_pagos_del_dia_report_summary(_filters_for_pagos_dia(filters))
	return get_recaudacion_por_concepto_report_summary(filters)
