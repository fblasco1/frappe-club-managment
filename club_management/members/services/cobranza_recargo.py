"""Recargo por mora al segundo vencimiento (spec cobranza_recargo_segundo_vencimiento.md)."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	erpnext_cobranza_disponible,
	get_club_settings,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	es_dia_segundo_vencimiento,
	format_periodo_cobro,
	periodo_recargo,
)

RECARGO_SUFFIX = "-REC"


def calcular_monto_recargo(saldo_pendiente: float, recargo_pct: float) -> float:
	"""Monto de recargo sobre saldo impago al 2.º vencimiento."""
	return flt(saldo_pendiente) * flt(recargo_pct) / 100.0


def recargo_periodo_existe(socio_name: str, periodo: str) -> bool:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		return False
	return bool(
		frappe.db.exists(
			SALES_INVOICE_DOCTYPE,
			{
				campo_socio: socio_name,
				campo_periodo: periodo_recargo(periodo),
				"docstatus": ["!=", 2],
			},
		)
	)


def facturas_mensuales_impagas_periodo(
	periodo: str,
	*,
	socio_name: str | None = None,
) -> list[dict[str, Any]]:
	"""Facturas mensuales del período con saldo pendiente (excluye recargos)."""
	if not erpnext_cobranza_disponible():
		return []

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		return []

	filters: dict[str, Any] = {
		campo_periodo: periodo,
		"docstatus": 1,
		"outstanding_amount": [">", 0],
	}
	if socio_name:
		filters[campo_socio] = socio_name

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=filters,
		fields=["name", campo_socio, "outstanding_amount", "due_date"],
	)
	return [
		{
			"name": row.name,
			"socio": row.get(campo_socio),
			"outstanding_amount": flt(row.outstanding_amount),
			"due_date": row.due_date,
		}
		for row in rows
		if row.get(campo_socio)
	]


def aplicar_recargo_factura_mensual(
	invoice_name: str,
	*,
	reference_date: str | None = None,
) -> str | None:
	"""Crea factura de recargo (opción A) para una factura mensual impaga."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	settings = get_club_settings()
	item_recargo = (settings.item_recargo_mora or "").strip()
	if not item_recargo or not frappe.db.exists("Item", item_recargo):
		frappe.throw(_("Configure el ítem de recargo mora en Club Settings."), frappe.ValidationError)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		frappe.throw(_("Falta configuración de factura mensual (migrate)."), frappe.ValidationError)

	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	socio_name = invoice.get(campo_socio)
	periodo = invoice.get(campo_periodo) or ""
	if not socio_name or not periodo or periodo.endswith(RECARGO_SUFFIX):
		return None

	from club_management.members.services.mora_al_cobro import factura_exenta_de_mora

	if factura_exenta_de_mora(invoice_name):
		return None

	saldo = flt(invoice.outstanding_amount)
	if saldo <= 0:
		return None
	if recargo_periodo_existe(socio_name, periodo):
		return None

	monto_recargo = calcular_monto_recargo(saldo, flt(settings.recargo_segundo_vencimiento_pct or 0))
	if monto_recargo <= 0:
		return None

	ref = getdate(reference_date or today())
	recargo_invoice = frappe.get_doc(
		{
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": invoice.customer,
			"company": invoice.company or _default_company(),
			"posting_date": ref,
			"due_date": ref,
			campo_socio: socio_name,
			campo_periodo: periodo_recargo(periodo),
			"remarks": _("Recargo mora período {0}").format(periodo),
			"items": [
				{
					"item_code": item_recargo,
					"qty": 1,
					"rate": monto_recargo,
					"description": _("Recargo 2.º vencimiento {0}").format(periodo),
				}
			],
		}
	)
	recargo_invoice.insert(ignore_permissions=True)
	recargo_invoice.submit()
	sync_saldo_deuda_socio(socio_name)
	return recargo_invoice.name


def aplicar_recargos_segundo_vencimiento(
	*,
	reference_date: str | None = None,
) -> dict[str, Any]:
	"""Aplica recargos a todas las facturas mensuales impagas del período."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	creadas: list[str] = []
	omitidas: list[str] = []
	errores: list[dict[str, str]] = []

	for row in facturas_mensuales_impagas_periodo(periodo):
		try:
			recargo_name = aplicar_recargo_factura_mensual(row["name"], reference_date=str(ref))
			if recargo_name:
				creadas.append(recargo_name)
			else:
				omitidas.append(row["name"])
		except Exception as exc:
			errores.append({"factura": row["name"], "socio": row["socio"], "error": str(exc)})
			frappe.log_error(
				title=_("Recargo mora — error en factura {0}").format(row["name"]),
				message=frappe.get_traceback(),
			)

	result = {
		"periodo": periodo,
		"reference_date": str(ref),
		"recargos_creados": len(creadas),
		"facturas_omitidas": len(omitidas),
		"errores": len(errores),
		"recargo_names": creadas,
		"detalle_errores": errores,
	}
	frappe.logger("club_management.cobranza").info("aplicar_recargos_segundo_vencimiento %s", result)
	return result
