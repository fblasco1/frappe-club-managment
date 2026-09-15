"""Wrappers de informes contables ERPNext para Tesorería (P&L y Cash Flow).

No reimplementan el mayor: delegan en `erpnext.accounts.report`.
Spec: `informes_tesoreria_pnl_cashflow.md`.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, getdate

from club_management.finance.permissions import ensure_tesoreria_access, user_has_tesoreria_access
from club_management.setup.icdpe_company import resolve_icdpe_company

REPORTE_GANANCIAS_PERDIDAS = "Ganancias y Perdidas"
REPORTE_FLUJO_EFECTIVO = "Flujo de Efectivo"
REPORTE_FLUJO_OPERATIVO = "Proyeccion Flujo de Fondos"

InformeResult = tuple[list[dict[str, Any]], list[Any], Any, Any, Any]


def informes_contables_panel() -> dict[str, Any]:
	"""Nombres de reportes para el panel. `visible` solo para Tesorería."""
	return {
		"visible": user_has_tesoreria_access(),
		"ganancias_perdidas": REPORTE_GANANCIAS_PERDIDAS,
		"flujo_efectivo": REPORTE_FLUJO_EFECTIVO,
		"flujo_operativo": REPORTE_FLUJO_OPERATIVO,
	}


def default_informe_filters(filters: dict[str, Any] | None = None) -> frappe._dict:
	"""Período mes en curso, company ICDPE, Date Range mensual."""
	raw = frappe._dict(filters or {})
	hoy = getdate()
	company = raw.get("company") or resolve_icdpe_company()
	return frappe._dict(
		{
			"company": company,
			"filter_based_on": "Date Range",
			"period_start_date": getdate(raw.get("period_start_date") or get_first_day(hoy)),
			"period_end_date": getdate(raw.get("period_end_date") or hoy),
			"periodicity": raw.get("periodicity") or "Monthly",
			"accumulated_values": cint(raw.get("accumulated_values") or 0),
			"include_default_book_entries": 1,
			"cost_center": raw.get("cost_center") or None,
			"from_fiscal_year": raw.get("from_fiscal_year"),
			"to_fiscal_year": raw.get("to_fiscal_year"),
			"selected_view": raw.get("selected_view") or "Report",
		}
	)


def _asegurar_erpnext() -> None:
	if not frappe.db.exists("DocType", "Account"):
		frappe.throw(_("ERPNext no está disponible."), frappe.ValidationError)
	if frappe.db.db_type == "postgres":
		from club_management.integrations.payment_ledger_postgres import apply_patch

		apply_patch()


def _normalizar_resultado(result: Any) -> InformeResult:
	cols = result[0] if result else []
	data = result[1] if result and len(result) > 1 else []
	message = result[2] if result and len(result) > 2 else None
	chart = result[3] if result and len(result) > 3 else None
	summary = result[4] if result and len(result) > 4 else None
	return cols, data, message, chart, summary


def ejecutar_ganancias_y_perdidas(
	filters: dict[str, Any] | None = None,
) -> InformeResult:
	ensure_tesoreria_access()
	_asegurar_erpnext()
	from erpnext.accounts.report.profit_and_loss_statement.profit_and_loss_statement import (
		execute as pnl_execute,
	)

	return _normalizar_resultado(pnl_execute(default_informe_filters(filters)))


def ejecutar_flujo_de_efectivo(
	filters: dict[str, Any] | None = None,
) -> InformeResult:
	ensure_tesoreria_access()
	_asegurar_erpnext()
	from erpnext.accounts.report.cash_flow.cash_flow import execute as cash_flow_execute

	return _normalizar_resultado(cash_flow_execute(default_informe_filters(filters)))
