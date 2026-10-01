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
