"""API Desk: carga rápida ingreso/egreso (Secretaría)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from club_management.finance.permissions import ensure_carga_rapida_access
from club_management.finance.services.carga_rapida import registrar_egreso, registrar_ingreso
from club_management.members.services.modos_pago_desk import list_modos_pago_cobranza_payload


@frappe.whitelist()
def registrar_ingreso_rapido(
	item_code: str,
	amount: float | str,
	cost_center: str | None = None,
	customer: str | None = None,
	posting_date: str | None = None,
	due_date: str | None = None,
	cobrado_ahora: int | str | None = 0,
	mode_of_payment: str | None = None,
	club_concepto: str | None = None,
	remarks: str | None = None,
) -> dict:
	ensure_carga_rapida_access()
	return registrar_ingreso(
		item_code=item_code,
		amount=float(amount),
		cost_center=cost_center or None,
		customer=customer or None,
		posting_date=posting_date or None,
		due_date=due_date or None,
		cobrado_ahora=bool(cint(cobrado_ahora)),
		mode_of_payment=mode_of_payment,
		club_concepto=club_concepto or None,
		remarks=remarks or None,
	)


@frappe.whitelist()
def registrar_egreso_rapido(
	supplier: str,
	item_code: str,
	amount: float | str,
	due_date: str,
	cost_center: str | None = None,
	posting_date: str | None = None,
	pagado_ahora: int | str | None = 0,
	mode_of_payment: str | None = None,
	club_concepto: str | None = None,
	remarks: str | None = None,
) -> dict:
	ensure_carga_rapida_access()
	if not due_date:
		frappe.throw(_("due_date es obligatorio."), frappe.ValidationError)
	return registrar_egreso(
		supplier=supplier,
		item_code=item_code,
		amount=float(amount),
		due_date=due_date,
		cost_center=cost_center or None,
		posting_date=posting_date or None,
		pagado_ahora=bool(cint(pagado_ahora)),
		mode_of_payment=mode_of_payment,
		club_concepto=club_concepto or None,
		remarks=remarks or None,
	)


@frappe.whitelist()
def list_modos_pago_finanzas() -> list[dict[str, str]]:
	ensure_carga_rapida_access()
	return list_modos_pago_cobranza_payload()
