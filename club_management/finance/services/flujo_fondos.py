"""Proyección de flujo de fondos (liquidez días 1–N)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate

from club_management.finance.permissions import ensure_tesoreria_access
from club_management.setup.icdpe_company import resolve_icdpe_company

# Día del mes en que se proyecta la liquidación Cobros Plus / cuotas+aranceles.
COBROS_PLUS_DIA_MES = 10
# Segundo hito de mora proyectada en cobros_mes (alineado a tendencia KPI).
COBROS_SEGUNDO_HITO_DIA = 20
CONCEPTOS_CRITICOS = frozenset({"Personal", "Estructura"})
VENTANA_DIAS_DEFAULT = 5


def _as_of(as_of_date: str | date | None) -> date:
	return getdate(as_of_date) if as_of_date else getdate()


def get_saldo_caja_bancos(company: str, as_of_date: date | None = None) -> float:
	"""Suma debit−credit de cuentas Cash/Bank (PostgreSQL-safe)."""
	as_of = as_of_date or getdate()
	rows = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(g.debit - g.credit), 0) AS balance
		FROM "tabGL Entry" g
		INNER JOIN "tabAccount" a ON a.name = g.account
		WHERE g.company = %s
			AND g.is_cancelled = 0
			AND g.posting_date <= %s
			AND a.account_type IN ('Cash', 'Bank')
			AND a.is_group = 0
		""",
		(company, as_of),
	)
	return flt(rows[0][0] if rows else 0)


def get_pagos_comprometidos(
	company: str,
	*,
	as_of_date: date,
	ventana_dias: int,
) -> dict[str, Any]:
	"""Purchase Invoices outstanding con due_date en [as_of, as_of+N]."""
	hasta = add_days(as_of_date, ventana_dias)
	has_concepto = frappe.get_meta("Purchase Invoice").has_field("club_concepto")
	fields = ["name", "supplier", "due_date", "outstanding_amount", "grand_total"]
	if has_concepto:
		fields.append("club_concepto")

	invoices = frappe.get_all(
		"Purchase Invoice",
		filters={
			"company": company,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"due_date": ["between", [as_of_date, hasta]],
		},
		fields=fields,
		order_by="due_date asc",
	)

	por_concepto: dict[str, float] = {}
	total = 0.0
	criticas = 0.0
	detalle: list[dict[str, Any]] = []
	for inv in invoices:
		monto = flt(inv.outstanding_amount)
		total += monto
		concepto = (inv.get("club_concepto") or "Sin categoría") if has_concepto else "Sin categoría"
		por_concepto[concepto] = por_concepto.get(concepto, 0.0) + monto
		if concepto in CONCEPTOS_CRITICOS:
			criticas += monto
		detalle.append(
			{
				"name": inv.name,
				"supplier": inv.supplier,
				"due_date": str(inv.due_date),
				"outstanding_amount": monto,
				"club_concepto": concepto,
			}
		)

	return {
		"total": total,
		"obligaciones_criticas": criticas,
		"por_concepto": por_concepto,
		"detalle": detalle,
		"hasta": str(hasta),
	}


def get_gastos_proyectados_pendientes(
	company: str,
	*,
	as_of_date: date,
	ventana_dias: int,
) -> dict[str, Any]:
	"""Facturas de compra en Borrador (docstatus=0) con due_date en la ventana.

	Son «Gastos proyectados / Pendientes de aprobación»: aún no generan deuda contable
	firme, pero Tesorería debe verlos para tener visibilidad total de compromisos.
	"""
	hasta = add_days(as_of_date, ventana_dias)
	has_concepto = frappe.get_meta("Purchase Invoice").has_field("club_concepto")
	fields = ["name", "supplier", "due_date", "grand_total"]
	if has_concepto:
		fields.append("club_concepto")

	invoices = frappe.get_all(
		"Purchase Invoice",
		filters={
			"company": company,
			"docstatus": 0,
			"due_date": ["between", [as_of_date, hasta]],
		},
		fields=fields,
		order_by="due_date asc",
	)

	por_concepto: dict[str, float] = {}
	total = 0.0
	detalle: list[dict[str, Any]] = []
	for inv in invoices:
		monto = flt(inv.grand_total)
		total += monto
		concepto = (inv.get("club_concepto") or "Sin categoría") if has_concepto else "Sin categoría"
		por_concepto[concepto] = por_concepto.get(concepto, 0.0) + monto
		detalle.append(
			{
				"name": inv.name,
				"supplier": inv.supplier,
				"due_date": str(inv.due_date),
				"grand_total": monto,
				"club_concepto": concepto,
			}
		)

	return {
		"total": total,
		"por_concepto": por_concepto,
		"detalle": detalle,
		"hasta": str(hasta),
	}


def _due_cobros_plus_date(as_of_date: date, cobros_plus_dia: int = COBROS_PLUS_DIA_MES) -> date:
	try:
		return as_of_date.replace(day=cobros_plus_dia)
	except ValueError:
		due_cobros = add_days(as_of_date.replace(day=1), 32).replace(day=1)
		return add_days(due_cobros, -1)


def _factor_mora_cobros_mes(
	as_of_date: date,
	*,
	due_cobros: date,
	segundo_hito_dia: int = COBROS_SEGUNDO_HITO_DIA,
	pct_post_primer: float = 10.0,
	pct_post_segundo: float = 5.0,
) -> float:
	"""Multiplicador sobre outstanding de la ola día 10 según as_of."""
	if as_of_date <= due_cobros:
		return 1.0
	try:
		segundo = due_cobros.replace(day=int(segundo_hito_dia))
	except ValueError:
		segundo = add_days(due_cobros.replace(day=1), 32).replace(day=1)
		segundo = add_days(segundo, -1)
	factor = 1.0 + flt(pct_post_primer) / 100.0
	if as_of_date > segundo:
		factor += flt(pct_post_segundo) / 100.0
	return factor


def _pct_mora_from_settings() -> tuple[float, float]:
	try:
		from club_management.members.services.cobranza_manual import get_club_settings

		settings = get_club_settings()
		pct1 = flt(getattr(settings, "recargo_post_vencimiento_pct", None) or 10)
		pct2 = flt(getattr(settings, "recargo_mes_vencido_pct", None) or 5)
		return pct1, pct2
	except Exception:
		return 10.0, 5.0


def get_cobros_proyectados(
	company: str,
	*,
	as_of_date: date,
	ventana_dias: int,
	cobros_plus_dia: int = COBROS_PLUS_DIA_MES,
) -> dict[str, Any]:
	"""Sales Invoices outstanding: ventana corta vs ola día 10 (con mora post venc.)."""
	hasta_ventana = add_days(as_of_date, ventana_dias)
	due_cobros = _due_cobros_plus_date(as_of_date, cobros_plus_dia)
	pct1, pct2 = _pct_mora_from_settings()
	factor_mes = _factor_mora_cobros_mes(
		as_of_date,
		due_cobros=due_cobros,
		pct_post_primer=pct1,
		pct_post_segundo=pct2,
	)

	# Ventana: solo vencimientos futuros/en rango desde as_of.
	invoices_ventana = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": company,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"due_date": ["between", [as_of_date, hasta_ventana]],
		},
		fields=["name", "customer", "due_date", "outstanding_amount"],
		order_by="due_date asc",
	)

	# Ola día 10 del mes: incluye vencidas si as_of > 10 (proyección con mora).
	invoices_mes = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": company,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"due_date": due_cobros,
		},
		fields=["name", "customer", "due_date", "outstanding_amount"],
		order_by="name asc",
	)

	en_ventana = 0.0
	detalle_ventana: list[dict[str, Any]] = []
	for inv in invoices_ventana:
		monto = flt(inv.outstanding_amount)
		en_ventana += monto
		detalle_ventana.append(
			{
				"name": inv.name,
				"customer": inv.customer,
				"due_date": str(getdate(inv.due_date)),
				"outstanding_amount": monto,
			}
		)

	en_mes_cobros_plus = 0.0
	detalle_mes: list[dict[str, Any]] = []
	for inv in invoices_mes:
		base = flt(inv.outstanding_amount)
		monto = round(base * factor_mes, 2)
		en_mes_cobros_plus += monto
		detalle_mes.append(
			{
				"name": inv.name,
				"customer": inv.customer,
				"due_date": str(getdate(inv.due_date)),
				"outstanding_amount": monto,
				"outstanding_base": base,
				"factor_mora": factor_mes,
			}
		)

	return {
		"cobros_proyectados_ventana": en_ventana,
		"cobros_proyectados_mes": en_mes_cobros_plus,
		"due_cobros_plus": str(due_cobros),
		"factor_mora_cobros_mes": factor_mes,
		"detalle_ventana": detalle_ventana,
		"detalle_mes": detalle_mes,
	}


def calcular_proyeccion_flujo_fondos(
	*,
	as_of_date: str | date | None = None,
	ventana_dias: int = VENTANA_DIAS_DEFAULT,
	company: str | None = None,
	skip_permission_check: bool = False,
) -> dict[str, Any]:
	"""Resumen de liquidez proyectada para Tesorería."""
	if not skip_permission_check:
		ensure_tesoreria_access()

	if not frappe.db.exists("DocType", "Purchase Invoice"):
		frappe.throw(_("ERPNext no está disponible."), frappe.ValidationError)

	as_of = _as_of(as_of_date)
	ventana = int(ventana_dias or VENTANA_DIAS_DEFAULT)
	if ventana < 1:
		frappe.throw(_("ventana_dias debe ser >= 1."), frappe.ValidationError)

	comp = company or resolve_icdpe_company()
	saldo = get_saldo_caja_bancos(comp, as_of)
	pagos = get_pagos_comprometidos(comp, as_of_date=as_of, ventana_dias=ventana)
	proyectados = get_gastos_proyectados_pendientes(comp, as_of_date=as_of, ventana_dias=ventana)
	cobros = get_cobros_proyectados(comp, as_of_date=as_of, ventana_dias=ventana)

	liquidez = saldo + cobros["cobros_proyectados_ventana"] - pagos["total"]
	criticas = pagos["obligaciones_criticas"]
	alcanza = (saldo + cobros["cobros_proyectados_ventana"]) >= criticas

	return {
		"as_of_date": str(as_of),
		"ventana_dias": ventana,
		"company": comp,
		"saldo_caja_bancos": saldo,
		"pagos_comprometidos": pagos["total"],
		"obligaciones_criticas": criticas,
		"pagos_por_concepto": pagos["por_concepto"],
		"pagos_detalle": pagos["detalle"],
		"gastos_proyectados_pendientes": proyectados["total"],
		"gastos_proyectados_por_concepto": proyectados["por_concepto"],
		"gastos_proyectados_detalle": proyectados["detalle"],
		"cobros_proyectados_ventana": cobros["cobros_proyectados_ventana"],
		"cobros_proyectados_mes": cobros["cobros_proyectados_mes"],
		"due_cobros_plus": cobros["due_cobros_plus"],
		"factor_mora_cobros_mes": cobros.get("factor_mora_cobros_mes", 1.0),
		"liquidez_proyectada": liquidez,
		"liquidez_alcanza": alcanza,
	}
