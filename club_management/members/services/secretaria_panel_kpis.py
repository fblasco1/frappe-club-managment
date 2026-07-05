"""KPIs del panel Desk Secretaría (socios y recaudación mensual)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from club_management.members.services.recibo_pago import format_monto_ar

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_item_arancel_inscripcion,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	get_club_settings,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	format_periodo_cobro,
)

SOCIO_DOCTYPE = "Socio"
ESTADOS_EXCLUIDOS_TOTAL = frozenset({"Baja"})
SALES_INVOICE_ITEM_DOCTYPE = "Sales Invoice Item"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
PAYMENT_ENTRY_REFERENCE_DOCTYPE = "Payment Entry Reference"
RECARGO_SUFFIX = "-REC"

CATEGORIAS_GRAFICO = ("Activo", "Menor", "Adherente", "Jubilado", "Vitalicio")
CATEGORIAS_HERMANO = frozenset({"2° Hermano", "3° Hermano"})
_EDAD_MAYORIA = 18

from club_management.members.services.modos_pago_desk import agrupar_modo_pago_chart


def _last_day_previous_month(reference: date) -> date:
	first_current = reference.replace(day=1)
	return first_current.replace(day=1) - timedelta(days=1)


def _pct(recaudado: float, emitido: float) -> float:
	if emitido <= 0:
		return 0.0
	return round(flt(recaudado) / flt(emitido) * 100, 1)


def count_socios_total(*, as_of: date | None = None) -> int:
	filters: dict[str, Any] = {"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)]}
	if as_of:
		filters["creation"] = ["<=", as_of]
	return frappe.db.count(SOCIO_DOCTYPE, filters)


def get_morosos_deuda_total() -> float:
	"""Suma de `saldo_deuda` de socios con estado Moroso."""
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": "Moroso"},
		pluck="saldo_deuda",
	)
	return sum(flt(value) for value in rows)


def _es_menor_edad(fecha_nacimiento: str | date | None, *, as_of: date) -> bool:
	if not fecha_nacimiento:
		return False
	nac = getdate(fecha_nacimiento)
	edad = as_of.year - nac.year - ((as_of.month, as_of.day) < (nac.month, nac.day))
	return edad < _EDAD_MAYORIA


def _categoria_grafico_socio(
	categoria: str,
	fecha_nacimiento: str | date | None,
	*,
	as_of: date,
) -> str | None:
	if categoria in CATEGORIAS_HERMANO:
		return "Menor" if _es_menor_edad(fecha_nacimiento, as_of=as_of) else "Activo"
	if categoria in CATEGORIAS_GRAFICO:
		return categoria
	return None


def get_socios_por_categoria(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Total socios activos (no Baja) desglosado por categoría del gráfico."""
	as_of = getdate(reference_date or today())
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)]},
		fields=["categoria", "fecha_nacimiento"],
	)
	categorias = {categoria: 0 for categoria in CATEGORIAS_GRAFICO}
	for row in rows:
		bucket = _categoria_grafico_socio(
			row.categoria or "",
			row.fecha_nacimiento,
			as_of=as_of,
		)
		if bucket:
			categorias[bucket] += 1
	total = sum(categorias.values())
	return {"total": total, **categorias}


def get_socios_por_segmento(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Compatibilidad: delega en get_socios_por_categoria."""
	return get_socios_por_categoria(reference_date=reference_date)


def count_altas_bajas_mes(*, reference_date: str | date | None = None) -> dict[str, int]:
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	altas = frappe.db.count(
		SOCIO_DOCTYPE,
		{
			"fecha_alta": ["between", [first, last]],
			"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)],
		},
	)
	bajas = frappe.db.count(
		SOCIO_DOCTYPE,
		{
			"estado": "Baja",
			"ultimo_cambio_estado_en": ["between", [f"{first} 00:00:00", f"{last} 23:59:59"]],
		},
	)
	return {"altas": altas, "bajas": bajas}


def _count_periodos_cuota_impagos(socio_name: str) -> int:
	if not erpnext_cobranza_disponible():
		return 0
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		return 0
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=["name", campo_periodo],
	)
	periodos: set[str] = set()
	for row in rows:
		periodo = (row.get(campo_periodo) or "").strip()
		if not periodo or periodo.endswith(RECARGO_SUFFIX):
			continue
		periodos.add(periodo)
	return len(periodos)


def get_mora_1_3_meses_payload() -> dict[str, Any]:
	"""Socios con 1–3 períodos mensuales impagos y monto total de su deuda."""
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)], "saldo_deuda": [">", 0]},
		fields=["name", "saldo_deuda"],
	)
	cantidad = 0
	monto = 0.0
	for row in rows:
		periodos = _count_periodos_cuota_impagos(row.name)
		if 1 <= periodos <= 3:
			cantidad += 1
			monto += flt(row.saldo_deuda)
	return {
		"cantidad": cantidad,
		"monto": monto,
		"monto_label": format_monto_ar(monto),
	}


def _finalize_tendencia_dias(dias: list[dict[str, Any]]) -> None:
	emitido_acum = 0.0
	recaudado_acum = 0.0
	for row in dias:
		emitido_acum += flt(row.pop("emitido_dia", 0))
		recaudado_acum += flt(row.pop("recaudado_dia", 0))
		row["recaudado"] = round(recaudado_acum, 2)
		row["deuda"] = round(max(emitido_acum - recaudado_acum, 0), 2)


def _dia_en_mes_periodo(
	posting_date: str | date | None,
	*,
	period_first: date,
	period_last: date,
	fallback_day: int,
) -> int | None:
	"""Mapea una fecha contable al día 1…N del mes del período visualizado."""
	if not posting_date:
		return min(max(int(fallback_day), 1), period_last.day)
	posting = getdate(posting_date)
	if period_first <= posting <= period_last:
		return posting.day
	if posting < period_first:
		return min(max(int(fallback_day), 1), period_last.day)
	return period_last.day


def get_recaudacion_tendencia_payload(
	*,
	reference_date: str | date | None = None,
) -> dict[str, Any]:
	"""Serie diaria acumulada: deuda pendiente vs recaudado (cuotas sociales) en un mes."""
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	periodo = format_periodo_cobro(ref)
	dias: list[dict[str, Any]] = [
		{"dia": day, "label": str(day), "emitido_dia": 0.0, "recaudado_dia": 0.0}
		for day in range(1, last.day + 1)
	]
	by_day = {row["dia"]: row for row in dias}
	payload: dict[str, Any] = {
		"periodo": periodo,
		"reference_date": str(first),
		"dias": dias,
		"disponible": False,
	}
	if not erpnext_cobranza_disponible():
		_finalize_tendencia_dias(dias)
		return payload

	campo_periodo = _campo_periodo_cobro()
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_periodo or not campo_socio:
		_finalize_tendencia_dias(dias)
		return payload

	settings = get_club_settings()
	cuota_items = _cuota_item_codes(settings)
	emit_day = int(settings.dia_generacion_deuda or 1)
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1},
		fields=["name", "posting_date", "grand_total"],
	)
	if not invoices:
		_finalize_tendencia_dias(dias)
		return {**payload, "dias": dias, "disponible": True}

	lines_by_parent = _invoice_lines_by_parent([row.name for row in invoices])
	invoice_by_name = {row.name: row for row in invoices}

	for invoice in invoices:
		day = _dia_en_mes_periodo(
			invoice.posting_date,
			period_first=first,
			period_last=last,
			fallback_day=emit_day,
		)
		if day is None:
			continue
		for line in lines_by_parent.get(invoice.name, []):
			if (line.get("item_code") or "") not in cuota_items:
				continue
			by_day[day]["emitido_dia"] += flt(line.get("amount"))

	pe_names = frappe.get_all(
		PAYMENT_ENTRY_REFERENCE_DOCTYPE,
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", list(invoice_by_name)],
			"parenttype": PAYMENT_ENTRY_DOCTYPE,
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	if pe_names:
		parent_names = sorted({row.parent for row in pe_names})
		pe_by_name = {
			row.name: row
			for row in frappe.get_all(
				PAYMENT_ENTRY_DOCTYPE,
				filters={
					"name": ["in", parent_names],
					"docstatus": 1,
				},
				fields=["name", "posting_date"],
			)
		}
		for ref in pe_names:
			pe = pe_by_name.get(ref.parent)
			invoice = invoice_by_name.get(ref.reference_name)
			if not pe or not invoice:
				continue
			grand_total = flt(invoice.grand_total)
			if grand_total <= 0:
				continue
			cuota_total = sum(
				flt(line.get("amount"))
				for line in lines_by_parent.get(invoice.name, [])
				if (line.get("item_code") or "") in cuota_items
			)
			if cuota_total <= 0:
				continue
			cuota_paid = flt(ref.allocated_amount) * (cuota_total / grand_total)
			day = _dia_en_mes_periodo(
				pe.posting_date,
				period_first=first,
				period_last=last,
				fallback_day=emit_day,
			)
			if day is None:
				continue
			by_day[day]["recaudado_dia"] += cuota_paid

	_finalize_tendencia_dias(dias)
	return {**payload, "dias": dias, "disponible": True}


def _agrupar_modo_pago(mode: str | None) -> str:
	return agrupar_modo_pago_chart(mode)


def get_medios_pago_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Distribución de cobros del mes por medio de pago agrupado."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	empty = {
		"periodo": periodo,
		"disponible": False,
		"efectivo": 0.0,
		"tarjeta": 0.0,
		"transferencia": 0.0,
		"otro": 0.0,
	}
	if not erpnext_cobranza_disponible():
		return empty
	if not frappe.db.exists("DocType", PAYMENT_ENTRY_DOCTYPE):
		return empty

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return empty

	first = get_first_day(ref)
	last = get_last_day(ref)
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_socio: ["is", "set"], "docstatus": 1},
		pluck="name",
	)
	if not invoices:
		return {**empty, "disponible": True}

	pe_names = frappe.get_all(
		PAYMENT_ENTRY_REFERENCE_DOCTYPE,
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", invoices],
			"parenttype": PAYMENT_ENTRY_DOCTYPE,
		},
		pluck="parent",
		distinct=True,
	)
	if not pe_names:
		return {**empty, "disponible": True}

	totals = {"efectivo": 0.0, "tarjeta": 0.0, "transferencia": 0.0, "otro": 0.0}
	for row in frappe.get_all(
		PAYMENT_ENTRY_DOCTYPE,
		filters={
			"name": ["in", pe_names],
			"docstatus": 1,
			"posting_date": ["between", [first, last]],
		},
		fields=["mode_of_payment", "paid_amount"],
	):
		key = _agrupar_modo_pago(row.mode_of_payment)
		totals[key] += flt(row.paid_amount)

	return {"periodo": periodo, "disponible": True, **totals}


def get_socio_metricas_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	segmentos = get_socios_por_categoria(reference_date=ref)
	total = segmentos["total"]
	total_mes_anterior = count_socios_total(as_of=_last_day_previous_month(ref))
	delta = total - total_mes_anterior
	morosos = frappe.db.count(SOCIO_DOCTYPE, {"estado": "Moroso"})
	morosos_deuda = get_morosos_deuda_total()
	mora_1_3 = get_mora_1_3_meses_payload()
	return {
		"total": total,
		"segmentos": segmentos,
		"total_mes_anterior": total_mes_anterior,
		"delta_mes": delta,
		"altas_bajas": count_altas_bajas_mes(reference_date=ref),
		"morosos": morosos,
		"morosos_deuda": morosos_deuda,
		"morosos_deuda_label": format_monto_ar(morosos_deuda),
		"mora_1_3": mora_1_3,
	}


def _cuota_item_codes(settings: frappe._dict) -> set[str]:
	codes = {settings.item_cuota_social}
	for row in settings.cuotas_categoria or []:
		if row.item:
			codes.add(row.item)
	return {code for code in codes if code}


def _arancel_item_actividad_map() -> dict[str, str]:
	mapping: dict[str, str] = {}
	if not frappe.db.table_exists(INSCRIPCION_DOCTYPE):
		return mapping
	for row in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": "Activa"},
		fields=["name", "actividad"],
	):
		item_code = resolve_item_arancel_inscripcion(row.name)
		if item_code and row.actividad:
			mapping[item_code] = row.actividad
	return mapping


def _invoice_lines_by_parent(invoice_names: list[str]) -> dict[str, list[dict[str, Any]]]:
	if not invoice_names:
		return {}
	rows = frappe.get_all(
		SALES_INVOICE_ITEM_DOCTYPE,
		filters={"parent": ["in", invoice_names], "docstatus": ["<", 2]},
		fields=["parent", "item_code", "amount"],
	)
	grouped: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _cuotas_sociales_kpi_payload(*, emitido: float, recaudado: float) -> dict[str, Any]:
	pendiente = max(flt(emitido) - flt(recaudado), 0.0)
	return {
		"emitido": emitido,
		"recaudado": recaudado,
		"saldo_por_cobrar": pendiente,
		"recaudado_label": format_monto_ar(recaudado),
		"saldo_por_cobrar_label": format_monto_ar(pendiente),
		"porcentaje": _pct(recaudado, emitido),
	}


def get_recaudacion_mes_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Recaudación de cuotas y aranceles del período MM/YYYY."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	empty = {
		"periodo": periodo,
		"cuotas_sociales": _cuotas_sociales_kpi_payload(emitido=0.0, recaudado=0.0),
		"aranceles": {"porcentaje": 0.0, "emitido": 0.0, "recaudado": 0.0, "por_actividad": []},
		"disponible": False,
	}
	if not erpnext_cobranza_disponible():
		return empty

	campo_periodo = _campo_periodo_cobro()
	if not campo_periodo or not _campo_socio_en(SALES_INVOICE_DOCTYPE):
		return empty

	settings = get_club_settings()
	cuota_items = _cuota_item_codes(settings)
	arancel_map = _arancel_item_actividad_map()

	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1},
		fields=["name", "grand_total", "outstanding_amount"],
	)
	lines_by_parent = _invoice_lines_by_parent([row.name for row in invoices])

	cuota_emitido = 0.0
	cuota_recaudado = 0.0
	arancel_emitido = 0.0
	arancel_recaudado = 0.0
	actividad_emitido: dict[str, float] = {}
	actividad_recaudado: dict[str, float] = {}

	for invoice in invoices:
		grand_total = flt(invoice.grand_total)
		if grand_total <= 0:
			continue
		paid_ratio = max(flt(invoice.grand_total) - flt(invoice.outstanding_amount), 0) / grand_total
		for line in lines_by_parent.get(invoice.name, []):
			amount = flt(line.amount)
			if amount <= 0:
				continue
			item_code = line.item_code or ""
			paid = amount * paid_ratio
			if item_code in cuota_items:
				cuota_emitido += amount
				cuota_recaudado += paid
				continue
			actividad = arancel_map.get(item_code)
			if not actividad:
				continue
			arancel_emitido += amount
			arancel_recaudado += paid
			actividad_emitido[actividad] = actividad_emitido.get(actividad, 0.0) + amount
			actividad_recaudado[actividad] = actividad_recaudado.get(actividad, 0.0) + paid

	por_actividad = []
	for actividad in sorted(actividad_emitido):
		emitido = actividad_emitido[actividad]
		recaudado = actividad_recaudado.get(actividad, 0.0)
		por_actividad.append(
			{
				"actividad": actividad,
				"emitido": emitido,
				"recaudado": recaudado,
				"porcentaje": _pct(recaudado, emitido),
			}
		)

	return {
		"periodo": periodo,
		"disponible": True,
		"cuotas_sociales": _cuotas_sociales_kpi_payload(
			emitido=cuota_emitido,
			recaudado=cuota_recaudado,
		),
		"aranceles": {
			"emitido": arancel_emitido,
			"recaudado": arancel_recaudado,
			"porcentaje": _pct(arancel_recaudado, arancel_emitido),
			"por_actividad": por_actividad,
		},
	}


def get_panel_metricas_payload(
	*,
	reference_date: str | date | None = None,
	tendencia_reference_date: str | date | None = None,
) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	tendencia_ref = getdate(tendencia_reference_date or ref)
	socios = get_socio_metricas_payload(reference_date=ref)
	recaudacion = get_recaudacion_mes_payload(reference_date=ref)
	return {
		"socios": socios,
		"recaudacion": recaudacion,
		"tendencia_recaudacion": get_recaudacion_tendencia_payload(reference_date=tendencia_ref),
		"medios_pago": get_medios_pago_payload(reference_date=ref),
		"ver_mas": {
			"socios_morosos_doctype": SOCIO_DOCTYPE,
			"socios_morosos_filters": [["Socio", "estado", "=", "Moroso"]],
			"socios_total_doctype": SOCIO_DOCTYPE,
			"socios_total_filters": [["Socio", "estado", "!=", "Baja"]],
			"socios_deuda_doctype": SOCIO_DOCTYPE,
			"socios_deuda_filters": [["Socio", "saldo_deuda", ">", 0]],
			"solicitudes_doctype": "Solicitud Asociacion",
			"solicitudes_filters": [
				["Solicitud Asociacion", "workflow_state", "in", ["Pendiente", "Requiere Corrección"]]
			],
		},
	}
