"""API Desk — cobranza manual (Secretaría)."""

from __future__ import annotations

import frappe

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cargo_socio import (
	cancelar_cargo_socio as _cancelar_cargo_socio,
	facturar_cargo_socio as _facturar_cargo_socio,
)
from club_management.members.services.cobranza_manual import (
	cancelar_factura_venta_impaga,
	ensure_customer_for_socio,
	generar_cargo_socio,
	get_detalle_deuda_socio,
	list_facturas_impagas_cancelables_socio,
	list_facturas_pendientes_socio,
	list_historial_pagos_socio,
	registrar_cobro_compuesto as _registrar_cobro_compuesto,
	sync_saldo_deuda_socio,
)
from club_management.members.services.modos_pago_desk import list_modos_pago_cobranza_payload
from club_management.members.services.recibo_pago import build_recibo_pago
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


@frappe.whitelist()
def crear_cliente_socio(socio: str) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	customer = ensure_customer_for_socio(socio)
	return {"status": "ok", "customer": customer}


@frappe.whitelist()
def generar_cargo(
	socio: str,
	incluir_actividades: int = 1,
	reference_date: str | None = None,
	periodo: str | None = None,
) -> dict[str, str | float | list[str]]:
	from club_management.members.services.cobranza_manual import reference_date_desde_periodo

	apply_patch()
	ensure_secretaria_operacion_access()
	ref = reference_date
	if not ref and periodo:
		ref = str(reference_date_desde_periodo(periodo))
	invoices = generar_cargo_socio(
		socio,
		incluir_actividades=bool(incluir_actividades),
		reference_date=ref,
	)
	saldo = sync_saldo_deuda_socio(socio)
	return {
		"status": "ok",
		"sales_invoices": invoices,
		"sales_invoice": invoices[0] if invoices else "",
		"saldo_deuda": saldo,
		"periodo": periodo or "",
		"reference_date": ref or "",
	}


@frappe.whitelist()
def generar_deuda_rango(
	socio: str,
	desde: str,
	hasta: str,
) -> dict:
	from club_management.members.services.cobranza_periodica import generar_deuda_rango_meses

	ensure_secretaria_operacion_access()
	return generar_deuda_rango_meses(socio, desde=desde, hasta=hasta)


@frappe.whitelist()
def list_facturas_pendientes(socio: str) -> list[dict]:
	ensure_secretaria_operacion_access()
	return list_facturas_pendientes_socio(socio)


@frappe.whitelist()
def list_facturas_impagas_cancelables(socio: str) -> list[dict]:
	ensure_secretaria_operacion_access()
	return list_facturas_impagas_cancelables_socio(socio)


@frappe.whitelist()
def cancelar_factura_venta(socio: str, sales_invoice: str) -> dict[str, str | float]:
	apply_patch()
	ensure_secretaria_operacion_access()
	return cancelar_factura_venta_impaga(socio, sales_invoice)


@frappe.whitelist()
def list_detalle_deuda(socio: str) -> dict:
	ensure_secretaria_operacion_access()
	return get_detalle_deuda_socio(socio)


@frappe.whitelist()
def list_historial_pagos(socio: str, limit: int = 50) -> list[dict]:
	ensure_secretaria_operacion_access()
	return list_historial_pagos_socio(socio, limit=int(limit or 50))


@frappe.whitelist()
def list_modos_pago_cobranza() -> list[dict[str, str]]:
	ensure_secretaria_operacion_access()
	return list_modos_pago_cobranza_payload()


@frappe.whitelist()
def preview_mora_al_cobro(
	socio: str,
	sales_invoices: str | list | None = None,
	posting_date: str | None = None,
) -> dict:
	"""Calcula total exigido con mora **sin** crear SI ni Payment Entry (preview Desk)."""
	from club_management.members.services.mora_al_cobro import previsualizar_cobro_con_mora

	ensure_secretaria_operacion_access()
	invoices: list[str] = []
	if sales_invoices:
		parsed = frappe.parse_json(sales_invoices) if isinstance(sales_invoices, str) else sales_invoices
		invoices = [str(x) for x in (parsed or []) if str(x).strip()]
	if not invoices:
		frappe.throw(frappe._("Seleccioná al menos una factura."), frappe.ValidationError)
	return previsualizar_cobro_con_mora(socio, invoices, posting_date=posting_date)


@frappe.whitelist()
def registrar_cobro(
	socio: str,
	sales_invoice: str | None = None,
	sales_invoices: str | list | None = None,
	mode_of_payment: str | None = None,
	medios: str | list | None = None,
	posting_date: str | None = None,
) -> dict[str, str | float | list | dict | None]:
	from club_management.members.services.mora_al_cobro import preparar_facturas_cobro_con_mora

	ensure_secretaria_operacion_access()
	invoices: list[str] = []
	if sales_invoices:
		parsed = frappe.parse_json(sales_invoices) if isinstance(sales_invoices, str) else sales_invoices
		invoices = [str(x) for x in (parsed or [])]
	elif sales_invoice:
		invoices = [sales_invoice]
	else:
		frappe.throw(frappe._("Seleccioná al menos una factura."), frappe.ValidationError)

	prep = preparar_facturas_cobro_con_mora(socio, invoices, posting_date=posting_date)
	invoices = prep["sales_invoices"]

	medios_list: list[dict]
	if medios:
		parsed_medios = frappe.parse_json(medios) if isinstance(medios, str) else medios
		medios_list = list(parsed_medios or [])
	elif mode_of_payment:
		medios_list = [{"mode_of_payment": mode_of_payment, "amount": prep["total_exigido"]}]
	else:
		frappe.throw(frappe._("Indicá al menos un medio de pago."), frappe.ValidationError)

	result = _registrar_cobro_compuesto(
		socio,
		invoices,
		medios_list,
		posting_date=posting_date,
	)
	estado = frappe.db.get_value("Socio", socio, "estado")
	recibos = [build_recibo_pago(pe) for pe in result["payment_entries"]]
	return {
		"status": "ok",
		"payment_entries": result["payment_entries"],
		"payment_entry": result["payment_entries"][0],
		"saldo_deuda": result["saldo_deuda"],
		"estado": estado,
		"recibo": recibos[0] if recibos else None,
		"recibos": recibos,
		"total_exigido": prep["total_exigido"],
		"ajustes_mora": prep["ajustes"],
	}


@frappe.whitelist()
def registrar_cobro_compuesto(
	socio: str,
	sales_invoices: str | list,
	medios: str | list,
	posting_date: str | None = None,
) -> dict[str, str | float | list | dict | None]:
	"""API explícita para cobro multi-factura / medios mixtos (Desk)."""
	return registrar_cobro(
		socio=socio,
		sales_invoices=sales_invoices,
		medios=medios,
		posting_date=posting_date,
	)


@frappe.whitelist()
def get_recibo_pago(payment_entry: str) -> dict:
	ensure_secretaria_operacion_access()
	return build_recibo_pago(payment_entry)


@frappe.whitelist()
def actualizar_saldo_deuda(socio: str) -> dict[str, float]:
	ensure_secretaria_operacion_access()
	saldo = sync_saldo_deuda_socio(socio)
	return {"status": "ok", "saldo_deuda": saldo}


@frappe.whitelist()
def facturar_cargo_socio(cargo: str) -> dict[str, str | float]:
	apply_patch()
	return _facturar_cargo_socio(cargo)


@frappe.whitelist()
def cancelar_cargo_socio(cargo: str) -> dict[str, str]:
	return _cancelar_cargo_socio(cargo)
