"""Aplicación de `Bonificacion Recurrente` al armar la deuda mensual.

Spec: `gimnasio_cobro_socios_no_socios.md`. Solo afecta la línea de arancel de la
inscripción alcanzada; la beca vigente tiene prioridad (no se acumulan).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe.utils import flt, fmt_money, getdate, today

DOCTYPE = "Bonificacion Recurrente"


def bonificacion_recurrente_vigente(
	socio_name: str,
	inscripcion_name: str,
	*,
	reference_date: str | date | None = None,
) -> dict[str, Any] | None:
	if not frappe.db.exists("DocType", DOCTYPE):
		return None
	ins = frappe.db.get_value(
		"Inscripcion Actividad",
		inscripcion_name,
		["actividad", "grupo_actividad"],
		as_dict=True,
	)
	if not ins:
		return None
	ref = getdate(reference_date or today())
	rows = frappe.get_all(
		DOCTYPE,
		filters={
			"socio": socio_name,
			"actividad": ins.actividad,
			"estado": "Activa",
			"fecha_desde": ["<=", ref],
		},
		fields=["name", "tipo_descuento", "valor", "grupo_actividad", "fecha_hasta"],
		order_by="fecha_desde desc",
	)
	for row in rows:
		if row.fecha_hasta and getdate(row.fecha_hasta) < ref:
			continue
		if row.grupo_actividad and row.grupo_actividad != ins.grupo_actividad:
			continue
		return row
	return None


def aplicar_bonificacion_recurrente(
	socio_name: str,
	inscripcion_name: str,
	monto: float,
	*,
	reference_date: str | date | None = None,
) -> tuple[float, str | None]:
	"""Devuelve `(monto_bonificado, etiqueta)`; etiqueta `None` si no hay bonificación vigente."""
	bonif = bonificacion_recurrente_vigente(
		socio_name, inscripcion_name, reference_date=reference_date
	)
	if not bonif:
		return flt(monto), None
	valor = flt(bonif.valor)
	if bonif.tipo_descuento == "Porcentaje":
		neto = flt(monto) * (1 - valor / 100)
		etiqueta = f"bonif. {valor:g}%"
	else:
		neto = flt(monto) - valor
		etiqueta = f"bonif. {fmt_money(valor)}"
	return max(0.0, flt(neto, 2)), etiqueta


def _recurrente_en_periodo(
	socio_name: str,
	actividad: str,
	grupo_actividad: str | None,
	inicio: date,
	fin: date,
) -> dict[str, Any] | None:
	rows = frappe.get_all(
		DOCTYPE,
		filters={
			"socio": socio_name,
			"actividad": actividad,
			"estado": "Activa",
			"fecha_desde": ["<=", fin],
		},
		fields=["name", "tipo_descuento", "valor", "grupo_actividad", "fecha_hasta", "motivo"],
		order_by="fecha_desde desc",
	)
	for row in rows:
		if row.fecha_hasta and getdate(row.fecha_hasta) < inicio:
			continue
		if row.grupo_actividad and row.grupo_actividad != grupo_actividad:
			continue
		return row
	return None


def bonificaciones_recurrentes_al_cobro(invoice_name: str, socio_name: str) -> list[dict[str, Any]]:
	"""Recurrentes vigentes en el período de una factura emitida sin aplicarlas.

	La deuda mensual marca con «bonif.» la línea ya bonificada; esas no se vuelven a descontar.
	"""
	from frappe.utils import get_last_day

	from club_management.activities.services.inscripcion_socio import resolve_item_arancel_inscripcion
	from club_management.members.services.beca_socio import beca_vigente_socio
	from club_management.members.services.cobranza_manual import (
		SALES_INVOICE_DOCTYPE,
		_campo_periodo_cobro,
	)
	from club_management.members.services.mora_al_cobro import parse_periodo_cobro

	if not frappe.db.exists("DocType", DOCTYPE):
		return []
	campo_periodo = _campo_periodo_cobro()
	periodo = frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, campo_periodo) if campo_periodo else None
	inicio = parse_periodo_cobro(periodo)
	if not inicio:
		return []
	fin = getdate(get_last_day(inicio))
	if beca_vigente_socio(socio_name, reference_date=inicio):
		return []

	base_por_item: dict[str, float] = {}
	for row in frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["item_code", "description", "amount"],
	):
		if flt(row.amount) <= 0 or "bonif." in (row.description or "").lower():
			continue
		base_por_item[row.item_code] = flt(base_por_item.get(row.item_code, 0) + flt(row.amount), 2)

	resultado: list[dict[str, Any]] = []
	for ins in frappe.get_all(
		"Inscripcion Actividad",
		filters={"socio": socio_name, "estado": "Activa"},
		fields=["name", "actividad", "grupo_actividad"],
	):
		item_code = resolve_item_arancel_inscripcion(ins.name)
		base = base_por_item.pop(item_code, 0.0) if item_code else 0.0
		if base <= 0:
			continue
		bonif = _recurrente_en_periodo(socio_name, ins.actividad, ins.grupo_actividad, inicio, fin)
		if not bonif:
			continue
		valor = flt(bonif.valor)
		if bonif.tipo_descuento == "Porcentaje":
			monto = flt(base * valor / 100, 2)
		else:
			monto = min(flt(valor, 2), base)
		if monto <= 0:
			continue
		resultado.append(
			{
				"bonificacion": bonif.name,
				"monto": monto,
				"motivo": bonif.motivo or "",
				"tipo_descuento": bonif.tipo_descuento,
				"valor": valor,
			}
		)
	return resultado
