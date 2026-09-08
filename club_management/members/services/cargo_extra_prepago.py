"""Prepago / cancelación adelantada de cargos extras recurrentes.

Spec: `club_management/specs/cargo_extra_prepago_adelantado.md`
"""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	_submit_sales_invoice_concepto,
	cargo_extra_linea_facturada_en_periodo,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	reference_date_desde_periodo,
	resolve_cost_center_item,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_periodica import (
	_iter_primeros_de_mes,
	resolve_fechas_factura_mensual,
)
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)

CARGO_DOCTYPE = "Cargo Socio"


def _mes_inicio(d: date) -> date:
	return date(d.year, d.month, 1)


def list_meses_prepago_cargo(
	cargo_name: str,
	*,
	reference_date: str | date | None = None,
) -> list[dict[str, Any]]:
	"""Meses restantes del cargo recurrente aún no facturados."""
	ensure_secretaria_operacion_access()
	doc = frappe.get_doc(CARGO_DOCTYPE, cargo_name)
	if doc.modo_cobro != "Recurrente":
		frappe.throw(_("Solo aplica a cargos recurrentes."), frappe.ValidationError)
	if not doc.fecha_hasta:
		frappe.throw(_("El cargo recurrente debe tener fecha hasta."), frappe.ValidationError)

	hoy = getdate(reference_date or today())
	inicio = max(_mes_inicio(hoy), _mes_inicio(getdate(doc.fecha_desde)))
	fin = _mes_inicio(getdate(doc.fecha_hasta))
	if inicio > fin:
		return []

	rows: list[dict[str, Any]] = []
	for month_start in _iter_primeros_de_mes(inicio, fin):
		periodo = format_periodo_cobro(month_start)
		ya = cargo_extra_linea_facturada_en_periodo(doc.socio, periodo, doc.titulo)
		rows.append(
			{
				"periodo": periodo,
				"reference_date": str(month_start),
				"monto": flt(doc.monto),
				"ya_facturado": ya,
			}
		)
	return rows


def prepagar_cargo_socio(
	cargo_name: str,
	*,
	periodos: list[str] | None = None,
	reference_date: str | date | None = None,
) -> dict[str, Any]:
	"""Emite SI por cada período elegido (o todos los restantes si `periodos` es None)."""
	ensure_secretaria_operacion_access()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	doc = frappe.get_doc(CARGO_DOCTYPE, cargo_name)
	if doc.estado == "Cancelado":
		frappe.throw(_("No se puede prepagar un cargo cancelado."), frappe.ValidationError)
	if doc.modo_cobro != "Recurrente":
		frappe.throw(_("Solo se pueden prepagar cargos recurrentes."), frappe.ValidationError)
	if not doc.fecha_hasta:
		frappe.throw(_("El cargo recurrente debe tener fecha hasta."), frappe.ValidationError)

	hoy = getdate(reference_date or today())
	disponibles = {
		r["periodo"]: r
		for r in list_meses_prepago_cargo(cargo_name, reference_date=hoy)
	}
	if periodos is None:
		elegidos = [p for p, row in disponibles.items() if not row["ya_facturado"]]
	else:
		elegidos = [str(p).strip() for p in periodos if str(p).strip()]

	if not elegidos:
		return {
			"status": "ok",
			"cargo": cargo_name,
			"sales_invoices": [],
			"omitidos": [],
			"saldo_deuda": sync_saldo_deuda_socio(doc.socio),
		}

	vigencia_desde = _mes_inicio(getdate(doc.fecha_desde))
	vigencia_hasta = _mes_inicio(getdate(doc.fecha_hasta))
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		frappe.throw(_("Falta configuración de factura (migrate)."), frappe.ValidationError)

	customer = ensure_customer_for_socio(doc.socio, skip_permission_check=True)
	settings = frappe.get_single("Club Settings")
	dia_v1 = int(settings.dia_primer_vencimiento or 10)
	company = _default_company()
	cost_center = resolve_cost_center_item(doc.item, company)

	created: list[str] = []
	omitidos: list[str] = []
	apply_patch()

	for periodo in elegidos:
		ref = reference_date_desde_periodo(periodo)
		if ref < vigencia_desde or ref > vigencia_hasta:
			frappe.throw(
				_("El período {0} está fuera de la vigencia del cargo.").format(periodo),
				frappe.ValidationError,
			)
		if cargo_extra_linea_facturada_en_periodo(doc.socio, periodo, doc.titulo):
			omitidos.append(periodo)
			continue

		posting, due = resolve_fechas_factura_mensual(ref, dia_v1)
		item: dict[str, Any] = {
			"item_code": doc.item,
			"qty": 1,
			"rate": flt(doc.monto),
			"description": _("{0} ({1})").format(doc.titulo, periodo),
		}
		if cost_center:
			item["cost_center"] = cost_center

		name = _submit_sales_invoice_concepto(
			socio_name=doc.socio,
			customer=customer,
			campo_socio=campo_socio,
			periodo=periodo,
			posting=posting,
			due=due,
			item=item,
		)
		created.append(name)

	pendientes = [
		r["periodo"]
		for r in list_meses_prepago_cargo(cargo_name, reference_date=hoy)
		if not r["ya_facturado"]
	]
	if not pendientes and doc.estado == "Pendiente":
		doc.estado = "Facturado"
		if created:
			doc.sales_invoice = created[-1]
		doc.save(ignore_permissions=True)

	saldo = sync_saldo_deuda_socio(doc.socio)
	return {
		"status": "ok",
		"cargo": cargo_name,
		"sales_invoices": created,
		"omitidos": omitidos,
		"estado": frappe.db.get_value(CARGO_DOCTYPE, cargo_name, "estado"),
		"saldo_deuda": saldo,
	}

