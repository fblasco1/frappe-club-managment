"""Facturación y cancelación de cargos extra al socio."""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	sync_saldo_deuda_socio,
)
from club_management.integrations.payment_ledger_postgres import apply_patch
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
	invoice = frappe.get_doc(
		{
			"doctype": SALES_INVOICE_DOCTYPE,
			"customer": customer,
			"company": _default_company(),
			"posting_date": today(),
			"due_date": today(),
			campo_socio: doc.socio,
			"remarks": _("Cargo extra: {0}").format(doc.titulo),
			"items": [
				{
					"item_code": doc.item,
					"qty": 1,
					"rate": flt(doc.monto),
					"description": doc.titulo,
				}
			],
		}
	)
	apply_patch()
	invoice.insert(ignore_permissions=True)
	invoice.submit()

	doc.estado = "Facturado"
	doc.sales_invoice = invoice.name
	doc.save(ignore_permissions=True)
	saldo = sync_saldo_deuda_socio(doc.socio)

	return {
		"status": "ok",
		"cargo": cargo_name,
		"sales_invoice": invoice.name,
		"saldo_deuda": saldo,
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
