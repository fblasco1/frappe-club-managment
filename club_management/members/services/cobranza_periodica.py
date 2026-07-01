"""Generación mensual de deuda para socios (job programado).

Spec: `club_management/specs/cobranza_periodica_mensual.md`

La fuente única de facturación mensual es este job (`submit_invoice = 0` en suscripciones)."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_socio_en,
	_campo_periodo_cobro,
	_default_company,
	build_invoice_items_for_socio,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	factura_periodo_existe,
	format_periodo_cobro,
	get_club_settings,
	sync_saldo_deuda_socio,
)

ESTADOS_ELEGIBLES = frozenset({"Activo", "Moroso"})


def es_dia_generacion_deuda(reference_date: str | date | None = None) -> bool:
	settings = get_club_settings()
	dia = int(settings.dia_generacion_deuda or 1)
	return getdate(reference_date or today()).day == dia


def primer_vencimiento(reference_date: str | date, dia_primer_vencimiento: int) -> date:
	"""Primer vencimiento en el mismo mes calendario que la generación."""
	d = getdate(reference_date)
	ultimo = calendar.monthrange(d.year, d.month)[1]
	return date(d.year, d.month, min(int(dia_primer_vencimiento), ultimo))


def resolve_fechas_factura_mensual(
	reference_date: str | date,
	dia_primer_vencimiento: int,
) -> tuple[date, date]:
	"""Posting y vencimiento válidos para ERPNext (`due_date` >= `posting_date`)."""
	ref = getdate(reference_date)
	now = getdate(today())
	due = primer_vencimiento(ref, dia_primer_vencimiento)
	posting = ref if ref >= now else now
	if due < posting:
		due = posting
	return posting, due


def segundo_vencimiento(reference_date: str | date, dia_segundo_vencimiento: str) -> date:
	"""Segundo vencimiento del período (último día del mes o día fijo)."""
	d = getdate(reference_date)
	ultimo = calendar.monthrange(d.year, d.month)[1]
	opcion = (dia_segundo_vencimiento or "Ultimo dia del mes").strip()
	if opcion == "Ultimo dia del mes":
		return date(d.year, d.month, ultimo)
	return date(d.year, d.month, min(int(opcion), ultimo))


def es_dia_segundo_vencimiento(reference_date: str | date | None = None) -> bool:
	settings = get_club_settings()
	ref = getdate(reference_date or today())
	segundo = segundo_vencimiento(ref, settings.dia_segundo_vencimiento or "Ultimo dia del mes")
	return ref == segundo


def periodo_recargo(periodo_cobro: str) -> str:
	return f"{periodo_cobro}-REC"


def socios_elegibles_deuda_mensual() -> list[str]:
	return frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": ["in", list(ESTADOS_ELEGIBLES)]},
		pluck="name",
		order_by="name asc",
	)


def generar_deuda_mensual_socio(
	socio_name: str,
	*,
	reference_date: str | date | None = None,
	skip_if_exists: bool = True,
) -> str | None:
	"""Crea y submittea `Sales Invoice` mensual; devuelve `name` o `None` si omite."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	if skip_if_exists and factura_periodo_existe(socio_name, periodo):
		return None

	settings = get_club_settings()
	invoice_items = build_invoice_items_for_socio(
		socio_name,
		incluir_actividades=bool(settings.incluir_aranceles_en_deuda_mensual),
		incluir_cargos_extra=bool(settings.incluir_cargos_extra_en_deuda_mensual),
		reference_date=str(ref),
		periodo_cobro=periodo,
	)
	if not invoice_items:
		return None

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
	posting, due = resolve_fechas_factura_mensual(
		ref,
		int(settings.dia_primer_vencimiento or 10),
	)

	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": customer,
		"company": _default_company(),
		"posting_date": posting,
		"due_date": due,
		campo_socio: socio_name,
		"remarks": _("Cuota mensual {0}").format(periodo),
		"items": invoice_items,
	}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		payload[campo_periodo] = periodo

	invoice = frappe.get_doc(payload)
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	invoice.insert(ignore_permissions=True)
	invoice.submit()
	sync_saldo_deuda_socio(socio_name)
	return invoice.name


def generar_deuda_mensual_socios(
	*,
	reference_date: str | date | None = None,
) -> dict[str, Any]:
	"""Procesa todos los socios elegibles; devuelve resumen de ejecución."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	creadas: list[str] = []
	omitidas: list[str] = []
	errores: list[dict[str, str]] = []

	for socio_name in socios_elegibles_deuda_mensual():
		try:
			invoice_name = generar_deuda_mensual_socio(socio_name, reference_date=ref)
			if invoice_name:
				creadas.append(invoice_name)
			else:
				omitidas.append(socio_name)
		except Exception as exc:
			errores.append({"socio": socio_name, "error": str(exc)})
			frappe.log_error(
				title=_("Deuda mensual — error en socio {0}").format(socio_name),
				message=frappe.get_traceback(),
			)

	result = {
		"periodo": periodo,
		"reference_date": str(ref),
		"facturas_creadas": len(creadas),
		"socios_omitidos": len(omitidas),
		"errores": len(errores),
		"invoice_names": creadas,
		"detalle_errores": errores,
	}
	frappe.logger("club_management.cobranza").info("generar_deuda_mensual_socios %s", result)
	return result
