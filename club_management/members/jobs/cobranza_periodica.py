"""Scheduler: deuda mensual de socios.

Spec: `club_management/specs/cobranza_periodica_mensual.md` § Scheduler.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import frappe
from frappe.utils import getdate, today

from club_management.members.services.cobranza_manual import format_periodo_cobro, get_club_settings
from club_management.members.services.cobranza_periodica import (
	es_dia_segundo_vencimiento,
	generar_deuda_mensual_socios,
)
from club_management.members.services.cobranza_recargo import aplicar_recargos_segundo_vencimiento

# La frecuencia `daily` corre en la cola `default` (timeout 300 s); la generación
# completa tarda más de 10 min, por eso se encola aparte en `long`.
DEUDA_JOB_TIMEOUT = 2 * 60 * 60
MARCA_DEUDA_MENSUAL = "club_management_deuda_mensual_ultimo_periodo"
EJECUTAR_DEUDA_METHOD = "club_management.members.jobs.cobranza_periodica.ejecutar_generacion_deuda_mensual"


def _fecha_generacion_periodo(ref: date) -> date | None:
	"""Día de generación del mes de `ref` si `ref` cae en la ventana de (re)intento."""
	settings = get_club_settings()
	dia_generacion = int(settings.dia_generacion_deuda or 1)
	dia_vencimiento = int(settings.dia_primer_vencimiento or 10)
	if ref.day == dia_generacion or dia_generacion < ref.day < dia_vencimiento:
		return date(ref.year, ref.month, dia_generacion)
	return None


def run_generar_deuda_si_corresponde(reference_date: str | date | None = None) -> None:
	"""Job diario: encola la generación del período si corresponde y no está marcado como generado."""
	ref = getdate(reference_date or today())
	fecha_generacion = _fecha_generacion_periodo(ref)
	if not fecha_generacion:
		return
	periodo = format_periodo_cobro(fecha_generacion)
	if (frappe.db.get_global(MARCA_DEUDA_MENSUAL) or "") == periodo:
		return
	frappe.enqueue(
		EJECUTAR_DEUDA_METHOD,
		queue="long",
		timeout=DEUDA_JOB_TIMEOUT,
		job_id=f"deuda_mensual_{periodo.replace('/', '-')}",
		deduplicate=True,
		reference_date=str(fecha_generacion),
	)


def ejecutar_generacion_deuda_mensual(reference_date: str | date) -> dict[str, Any]:
	"""Ejecución en background: commit por socio, marca el período y deja resumen en Error Log."""
	ref = getdate(reference_date)
	resultado = generar_deuda_mensual_socios(reference_date=ref, commit_por_socio=True)
	periodo = resultado.get("periodo") or format_periodo_cobro(ref)
	frappe.db.set_global(MARCA_DEUDA_MENSUAL, periodo)
	resumen = {k: v for k, v in resultado.items() if k != "invoice_names"}
	frappe.log_error(
		title=f"Deuda mensual {periodo} — resumen",
		message=json.dumps(resumen, ensure_ascii=False, indent=2, default=str),
	)
	frappe.db.commit()
	return resultado


def run_recargos_si_corresponde() -> None:
	"""Legado, desprogramado: la mora se calcula al cobrar (spec recargos_mora_dos_tramos.md, D4)."""
	if not es_dia_segundo_vencimiento():
		return
	aplicar_recargos_segundo_vencimiento()
