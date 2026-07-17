# Copyright (c) 2026, fblasco1 and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from club_management.finance.permissions import ensure_tesoreria_access
from club_management.finance.services.flujo_fondos import (
	VENTANA_DIAS_DEFAULT,
	calcular_proyeccion_flujo_fondos,
)


def execute(
	filters: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], None, None, list[dict[str, Any]]]:
	ensure_tesoreria_access()
	filters = filters or {}
	proyeccion = calcular_proyeccion_flujo_fondos(
		as_of_date=filters.get("as_of_date"),
		ventana_dias=cint(filters.get("ventana_dias") or VENTANA_DIAS_DEFAULT),
	)

	columns = [
		{"label": _("Concepto"), "fieldname": "concepto", "fieldtype": "Data", "width": 280},
		{"label": _("Monto"), "fieldname": "monto", "fieldtype": "Currency", "width": 140},
		{"label": _("Detalle"), "fieldname": "detalle", "fieldtype": "Data", "width": 220},
	]

	data = [
		{
			"concepto": _("Saldo caja y bancos"),
			"monto": proyeccion["saldo_caja_bancos"],
			"detalle": proyeccion["as_of_date"],
		},
		{
			"concepto": _("Cobros proyectados (ventana)"),
			"monto": proyeccion["cobros_proyectados_ventana"],
			"detalle": _("{0} días").format(proyeccion["ventana_dias"]),
		},
		{
			"concepto": _("Pagos comprometidos (ventana)"),
			"monto": proyeccion["pagos_comprometidos"],
			"detalle": "",
		},
		{
			"concepto": _("Obligaciones críticas (Personal+Estructura)"),
			"monto": proyeccion["obligaciones_criticas"],
			"detalle": "",
		},
		{
			"concepto": _("Liquidez proyectada"),
			"monto": proyeccion["liquidez_proyectada"],
			"detalle": _("Alcanza") if proyeccion["liquidez_alcanza"] else _("No alcanza"),
		},
		{
			"concepto": _("Cobros proyectados mes (Cobros Plus día {0})").format(
				proyeccion["due_cobros_plus"]
			),
			"monto": proyeccion["cobros_proyectados_mes"],
			"detalle": proyeccion["due_cobros_plus"],
		},
	]

	for inv in proyeccion.get("pagos_detalle") or []:
		data.append(
			{
				"concepto": _("PI {0} — {1}").format(inv["name"], inv.get("club_concepto") or ""),
				"monto": inv["outstanding_amount"],
				"detalle": inv["due_date"],
			}
		)

	summary = [
		{
			"value": proyeccion["saldo_caja_bancos"],
			"label": _("Saldo caja/bancos"),
			"datatype": "Currency",
		},
		{
			"value": proyeccion["obligaciones_criticas"],
			"label": _("Obligaciones críticas"),
			"datatype": "Currency",
		},
		{
			"value": 1 if proyeccion["liquidez_alcanza"] else 0,
			"label": _("Liquidez alcanza"),
			"datatype": "Int",
		},
	]
	return columns, data, None, None, summary
