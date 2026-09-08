"""Facturación y cancelación de cargos extra al socio."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	_submit_sales_invoice_concepto,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	format_periodo_cobro,
	resolve_cost_center_item,
	sync_saldo_deuda_socio,
)
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)

CARGO_DOCTYPE = "Cargo Socio"


def facturar_cargo_socio(cargo_name: str) -> dict[str, Any]:
	"""Factura un cargo único pendiente y marca el documento como Facturado."""
	ensure_secretaria_operacion_access()
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	doc = frappe.get_doc(CARGO_DOCTYPE, cargo_name)
	if doc.estado != "Pendiente":
		frappe.throw(_("Solo se pueden facturar cargos pendientes."), frappe.ValidationError)
	if doc.modo_cobro != "Unico":
		frappe.throw(_("Solo los cargos de cobro único se facturan desde aquí."), frappe.ValidationError)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	customer = ensure_customer_for_socio(doc.socio, skip_permission_check=True)
	company = _default_company()
	periodo = format_periodo_cobro(today())
	cost_center = resolve_cost_center_item(doc.item, company)
	item: dict[str, Any] = {
		"item_code": doc.item,
		"qty": 1,
		"rate": flt(doc.monto),
		"description": doc.titulo,
	}
	if cost_center:
		item["cost_center"] = cost_center

	apply_patch()
	invoice_name = _submit_sales_invoice_concepto(
		socio_name=doc.socio,
		customer=customer,
		campo_socio=campo_socio,
		periodo=periodo,
		posting=today(),
		due=today(),
		item=item,
	)

	doc.estado = "Facturado"
	doc.sales_invoice = invoice_name
	doc.save(ignore_permissions=True)
	saldo = sync_saldo_deuda_socio(doc.socio)

	return {
		"status": "ok",
		"cargo": cargo_name,
		"sales_invoice": invoice_name,
		"sales_invoices": [invoice_name],
		"saldo_deuda": saldo,
	}


def facturar_mes_corriente_cargo(
	cargo_name: str,
	*,
	reference_date: str | None = None,
) -> dict[str, Any]:
	"""Emite la SI del mes corriente de un cargo recurrente (para cobrarlo ya)."""
	from club_management.members.services.cargo_extra_prepago import (
		list_meses_prepago_cargo,
		prepagar_cargo_socio,
	)

	ensure_secretaria_operacion_access()
	doc = frappe.get_doc(CARGO_DOCTYPE, cargo_name)
	if doc.modo_cobro != "Recurrente":
		frappe.throw(_("Solo los cargos recurrentes facturan el mes corriente así."), frappe.ValidationError)
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	disponibles = {
		row["periodo"]: row
		for row in list_meses_prepago_cargo(cargo_name, reference_date=ref)
	}
	if periodo not in disponibles:
		frappe.throw(
			_("El período {0} está fuera de la vigencia del cargo.").format(periodo),
			frappe.ValidationError,
		)
	result = prepagar_cargo_socio(
		cargo_name,
		periodos=[periodo],
		reference_date=reference_date,
	)
	result["sales_invoice"] = (result.get("sales_invoices") or [None])[0] or ""
	return result


def crear_cargo_extra_socio(
	*,
	socio: str,
	titulo: str,
	tipo_cargo: str,
	modo_cobro: str,
	item: str,
	monto: float,
	fecha_desde: str | None = None,
	fecha_hasta: str | None = None,
	observaciones: str | None = None,
	facturar_mes_corriente: bool = True,
) -> dict[str, Any]:
	"""Crea el cargo extra y lo deja cobrable (factura única o mes corriente)."""
	ensure_secretaria_operacion_access()
	if not socio or not frappe.db.exists("Socio", socio):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)

	payload: dict[str, Any] = {
		"doctype": CARGO_DOCTYPE,
		"socio": socio,
		"titulo": titulo,
		"tipo_cargo": tipo_cargo,
		"modo_cobro": modo_cobro,
		"item": item,
		"monto": flt(monto),
		"fecha_desde": fecha_desde or today(),
		"estado": "Pendiente",
	}
	if fecha_hasta:
		payload["fecha_hasta"] = fecha_hasta
	if observaciones:
		payload["observaciones"] = observaciones

	doc = frappe.get_doc(payload)
	doc.insert()

	sales_invoices: list[str] = []
	if doc.modo_cobro == "Unico" and doc.sales_invoice:
		sales_invoices = [doc.sales_invoice]
	elif doc.modo_cobro == "Recurrente" and facturar_mes_corriente:
		prepago = facturar_mes_corriente_cargo(doc.name)
		sales_invoices = list(prepago.get("sales_invoices") or [])
		doc.reload()

	saldo = sync_saldo_deuda_socio(socio)
	return {
		"status": "ok",
		"cargo": doc.name,
		"estado": doc.estado,
		"sales_invoice": sales_invoices[0] if sales_invoices else (doc.sales_invoice or ""),
		"sales_invoices": sales_invoices,
		"saldo_deuda": saldo,
		"socio": socio,
		"modo_cobro": doc.modo_cobro,
	}


def cancelar_cargo_socio(cargo_name: str) -> dict[str, str]:
	"""Cancela un cargo pendiente (no entra en deuda mensual)."""
	ensure_secretaria_operacion_access()
	doc = frappe.get_doc(CARGO_DOCTYPE, cargo_name)
	if doc.estado != "Pendiente":
		frappe.throw(_("Solo se pueden cancelar cargos pendientes."), frappe.ValidationError)
	doc.estado = "Cancelado"
	doc.save(ignore_permissions=True)
	return {"status": "ok", "cargo": cargo_name, "estado": "Cancelado"}
