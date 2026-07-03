"""API Desk — cobranza manual (Secretaría)."""

from __future__ import annotations

import frappe

from club_management.integrations.payment_ledger_postgres import apply_patch
from club_management.members.services.cargo_socio import (
	cancelar_cargo_socio as _cancelar_cargo_socio,
	facturar_cargo_socio as _facturar_cargo_socio,
)
from club_management.members.services.cobranza_manual import (
	ensure_customer_for_socio,
	generar_cargo_socio,
	get_detalle_deuda_socio,
	list_facturas_pendientes_socio,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)
from club_management.members.services.modos_pago_desk import list_modos_pago_cobranza_payload
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


@frappe.whitelist()
def crear_cliente_socio(socio: str) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	customer = ensure_customer_for_socio(socio)
	return {"status": "ok", "customer": customer}


@frappe.whitelist()
def generar_cargo(socio: str, incluir_actividades: int = 1) -> dict[str, str]:
	apply_patch()
	ensure_secretaria_operacion_access()
	invoice = generar_cargo_socio(socio, incluir_actividades=bool(incluir_actividades))
	saldo = sync_saldo_deuda_socio(socio)
	return {"status": "ok", "sales_invoice": invoice, "saldo_deuda": saldo}


@frappe.whitelist()
def list_facturas_pendientes(socio: str) -> list[dict]:
	ensure_secretaria_operacion_access()
	return list_facturas_pendientes_socio(socio)


@frappe.whitelist()
def list_detalle_deuda(socio: str) -> dict:
	ensure_secretaria_operacion_access()
	return get_detalle_deuda_socio(socio)


@frappe.whitelist()
def list_modos_pago_cobranza() -> list[dict[str, str]]:
	ensure_secretaria_operacion_access()
	return list_modos_pago_cobranza_payload()


@frappe.whitelist()
def registrar_cobro(
	socio: str,
	sales_invoice: str,
	mode_of_payment: str | None = None,
) -> dict[str, str]:
	ensure_secretaria_operacion_access()
	payment_entry = registrar_cobro_manual(
		socio,
		sales_invoice,
		mode_of_payment=mode_of_payment,
	)
	saldo = sync_saldo_deuda_socio(socio)
	estado = frappe.db.get_value("Socio", socio, "estado")
	recibo = build_recibo_pago(payment_entry)
	return {
		"status": "ok",
		"payment_entry": payment_entry,
		"saldo_deuda": saldo,
		"estado": estado,
		"recibo": recibo,
	}


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
