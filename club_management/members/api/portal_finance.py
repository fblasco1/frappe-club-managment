"""API autenticada de deuda y comprobantes del socio (BL-6d)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	list_historial_pagos_socio,
)
from club_management.members.services.portal_session import get_current_socio


def _serialize_date(value: Any) -> str | None:
	if not value:
		return None
	return str(value)


def _require_socio_sesion() -> Any:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return get_current_socio()


def _concepto_factura(invoice_name: str, remarks: str | None) -> str:
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		fields=["description", "item_code"],
		order_by="idx asc",
		limit=1,
	)
	if items:
		concepto = (items[0].description or items[0].item_code or "").strip()
		if concepto:
			return concepto
	return (remarks or invoice_name or "").strip()


def _facturas_exigibles(socio_name: str) -> list[dict[str, Any]]:
	if not erpnext_cobranza_disponible():
		return []
	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo:
		return []
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo: socio_name, "docstatus": 1, "outstanding_amount": [">", 0]},
		fields=["name", "posting_date", "due_date", "outstanding_amount", "remarks"],
		order_by="due_date asc, posting_date asc, name asc",
	)
	return [
		{
			"name": row.name,
			"posting_date": _serialize_date(row.posting_date),
			"due_date": _serialize_date(row.due_date),
			"outstanding_amount": flt(row.outstanding_amount),
			"concepto": _concepto_factura(row.name, row.remarks),
		}
		for row in rows
	]


def _recibo_url(payment_entry: str) -> str:
	return f"/printview?doctype={quote('Payment Entry')}&name={quote(payment_entry)}"


def _pagos_recientes(socio_name: str) -> list[dict[str, Any]]:
	rows = list_historial_pagos_socio(socio_name, limit=5)[:5]
	pagos: list[dict[str, Any]] = []
	for row in rows:
		name = str(row.get("payment_entry") or "")
		pagos.append(
			{
				"name": name,
				"posting_date": _serialize_date(row.get("posting_date")),
				"paid_amount": flt(row.get("paid_amount")),
				"mode_of_payment": row.get("mode_of_payment") or "",
				"recibo_url": _recibo_url(name) if name else "",
			}
		)
	return pagos


@frappe.whitelist()
def get_estado_cuenta_socio() -> dict[str, Any]:
	"""Deuda exigible e historial reciente de pagos del socio de sesión."""
	socio = _require_socio_sesion()
	return {
		"facturas_pendientes": _facturas_exigibles(socio.name),
		"pagos_recientes": _pagos_recientes(socio.name),
	}
