"""Evaluación automática de morosos post segundo vencimiento."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	es_dia_segundo_vencimiento,
	format_periodo_cobro,
	periodo_recargo,
)
from club_management.members.services.socio_transitions import cambiar_estado

ESTADOS_EVALUAR = frozenset({"Activo"})
RECARGO_SUFFIX = "-REC"


def saldo_periodo_corriente(socio_name: str, periodo: str) -> float:
	"""Saldo impago de cuota+aranceles del período (mensual + recargo), sin otros cargos."""
	if not erpnext_cobranza_disponible():
		return 0.0

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		return 0.0

	total = 0.0
	for periodo_valor in (periodo, periodo_recargo(periodo)):
		rows = frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={
				campo_socio: socio_name,
				campo_periodo: periodo_valor,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			pluck="outstanding_amount",
		)
		total += sum(flt(value) for value in rows)
	return total


def evaluar_socio_moroso(
	socio_name: str,
	*,
	reference_date: str | None = None,
) -> bool:
	"""Marca moroso si el período corriente tiene deuda de cuota/aranceles."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	if estado not in ESTADOS_EVALUAR:
		return False
	if saldo_periodo_corriente(socio_name, periodo) <= 0:
		return False

	cambiar_estado(
		socio_name,
		"Moroso",
		motivo=_("Moroso automático — impago período {0}").format(periodo),
	)
	return True


def evaluar_morosos_automatico(
	*,
	reference_date: str | None = None,
) -> dict[str, Any]:
	"""Evalúa socios activos con impago de cuota/aranceles del período."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	marcados: list[str] = []
	omitidos: list[str] = []

	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": "Activo"},
		pluck="name",
		order_by="name asc",
	)
	for socio_name in socios:
		if evaluar_socio_moroso(socio_name, reference_date=str(ref)):
			marcados.append(socio_name)
		else:
			omitidos.append(socio_name)

	result = {
		"periodo": periodo,
		"reference_date": str(ref),
		"socios_marcados_moroso": len(marcados),
		"socios_omitidos": len(omitidos),
		"socios": marcados,
	}
	frappe.logger("club_management.cobranza").info("evaluar_morosos_automatico %s", result)
	return result
