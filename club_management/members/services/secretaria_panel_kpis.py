"""KPIs del panel Desk Secretaría (socios y recaudación mensual)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe.utils import flt, fmt_money, getdate, today

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


def get_socio_metricas_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	total = count_socios_total()
	total_mes_anterior = count_socios_total(as_of=_last_day_previous_month(ref))
	delta = total - total_mes_anterior
	morosos = frappe.db.count(SOCIO_DOCTYPE, {"estado": "Moroso"})
	morosos_deuda = get_morosos_deuda_total()
	return {
		"total": total,
		"total_mes_anterior": total_mes_anterior,
		"delta_mes": delta,
		"morosos": morosos,
		"morosos_deuda": morosos_deuda,
		"morosos_deuda_label": fmt_money(morosos_deuda),
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


def get_recaudacion_mes_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Recaudación de cuotas y aranceles del período MM/YYYY."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	empty = {
		"periodo": periodo,
		"cuotas_sociales": {"porcentaje": 0.0, "emitido": 0.0, "recaudado": 0.0},
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
		"cuotas_sociales": {
			"emitido": cuota_emitido,
			"recaudado": cuota_recaudado,
			"porcentaje": _pct(cuota_recaudado, cuota_emitido),
		},
		"aranceles": {
			"emitido": arancel_emitido,
			"recaudado": arancel_recaudado,
			"porcentaje": _pct(arancel_recaudado, arancel_emitido),
			"por_actividad": por_actividad,
		},
	}


def get_panel_metricas_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	socios = get_socio_metricas_payload(reference_date=reference_date)
	recaudacion = get_recaudacion_mes_payload(reference_date=reference_date)
	return {
		"socios": socios,
		"recaudacion": recaudacion,
		"ver_mas": {
			"socios_morosos_doctype": SOCIO_DOCTYPE,
			"socios_morosos_filters": [["Socio", "estado", "=", "Moroso"]],
			"socios_total_doctype": SOCIO_DOCTYPE,
			"socios_total_filters": [["Socio", "estado", "!=", "Baja"]],
		},
	}
