"""Medios de pago Desk (cobranza manual y gráficos Secretaría)."""

from __future__ import annotations

from typing import Any

import frappe

MEDIO_PAGO_EFECTIVO = frozenset({"Cash", "Cheque"})
MEDIO_PAGO_TARJETA = frozenset({"Credit Card", "Bank Draft"})
MEDIO_PAGO_TRANSFERENCIA = frozenset({"Wire Transfer"})

DESK_MODOS_PAGO_COBRANZA: tuple[dict[str, str], ...] = (
	{"value": "Cash", "label": "Efectivo"},
	{"value": "Credit Card", "label": "Tarjeta (crédito)"},
	{"value": "Bank Draft", "label": "Tarjeta (débito)"},
	{"value": "Wire Transfer", "label": "Transferencia"},
	{"value": "Cheque", "label": "Cheque"},
)


def agrupar_modo_pago_chart(mode: str | None) -> str:
	mode = (mode or "").strip()
	if mode in MEDIO_PAGO_EFECTIVO:
		return "efectivo"
	if mode in MEDIO_PAGO_TARJETA:
		return "tarjeta"
	if mode in MEDIO_PAGO_TRANSFERENCIA:
		return "transferencia"
	return "otro"


def list_modos_pago_cobranza_payload() -> list[dict[str, str]]:
	"""Opciones de medio de pago para registrar cobro en Desk."""
	items: list[dict[str, str]] = []
	for row in DESK_MODOS_PAGO_COBRANZA:
		if frappe.db.exists("Mode of Payment", row["value"]):
			items.append({"value": row["value"], "label": frappe._(row["label"])})
	if not items:
		items.append({"value": "Cash", "label": frappe._("Efectivo")})
	return items


def validar_modo_pago_desk(mode_of_payment: str | None) -> str:
	mode = (mode_of_payment or "Cash").strip()
	allowed = {row["value"] for row in DESK_MODOS_PAGO_COBRANZA}
	if mode not in allowed:
		frappe.throw(
			frappe._("Medio de pago no permitido: {0}").format(mode),
			frappe.ValidationError,
		)
	if not frappe.db.exists("Mode of Payment", mode):
		frappe.throw(
			frappe._("El medio de pago {0} no está configurado en ERPNext.").format(mode),
			frappe.ValidationError,
		)
	return mode
