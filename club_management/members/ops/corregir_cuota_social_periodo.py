"""Corrige la cuota social de facturas de un período emitidas con montos viejos (enmienda).

Spec: `club_management/specs/correccion_cuota_social_periodo.md`.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import flt

from club_management.members.data.cuotas_sociales_vigentes import (
	CUOTA_SOCIAL_ITEM_CODE,
	CUOTAS_SOCIALES_ANTERIORES,
	CUOTAS_SOCIALES_VIGENTES,
)
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	get_club_settings,
	sync_saldo_deuda_socio,
)
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed

LEGACY_CUOTA_ITEM = "CLUB-Cuota-Social-Base"
_TOLERANCIA = 0.005


def _items_cuota_social() -> set[str]:
	settings = get_club_settings()
	items = {CUOTA_SOCIAL_ITEM_CODE, LEGACY_CUOTA_ITEM}
	if settings.item_cuota_social:
		items.add(settings.item_cuota_social)
	items.update(row.item for row in (settings.cuotas_categoria or []) if row.item)
	return items


def _igual(a: float, b: float) -> bool:
	return abs(flt(a) - flt(b)) <= _TOLERANCIA


def _clasificar(
	invoice: Any,
	*,
	campo_socio: str,
	items_cuota: set[str],
	categorias: dict[str, str],
	nuevos: dict[str, float],
	anteriores: dict[str, float],
) -> tuple[str, dict[str, Any]]:
	socio = invoice.get(campo_socio)
	categoria = categorias.get(socio) or ""
	base = {
		"factura": invoice.name,
		"socio": socio,
		"categoria": categoria,
		"grand_total": flt(invoice.grand_total),
	}
	lineas = [row for row in invoice.items if row.item_code in items_cuota]
	if not lineas:
		return "sin_cuota", base
	if flt(invoice.outstanding_amount) < flt(invoice.grand_total) - _TOLERANCIA:
		return "con_pagos", {**base, "montos": [flt(r.rate) for r in lineas]}

	nuevo = nuevos.get(categoria)
	anterior = anteriores.get(categoria)
	rates = [flt(r.rate) for r in lineas]
	if nuevo is not None and all(_igual(r, nuevo) for r in rates):
		return "ya_correctas", {**base, "monto": nuevo}
	if (
		nuevo is not None
		and anterior is not None
		and all(_igual(r, anterior) or _igual(r, nuevo) for r in rates)
	):
		return "a_corregir", {**base, "monto_anterior": anterior, "monto_nuevo": nuevo}
	return "revisar", {**base, "montos": rates, "anterior": anterior, "nuevo": nuevo}


def _enmendar(name: str, *, items_cuota: set[str], anterior: float, nuevo: float) -> str:
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	original = frappe.get_doc(SALES_INVOICE_DOCTYPE, name)
	original.cancel()

	nueva = frappe.copy_doc(original)
	nueva.docstatus = 0
	for child in nueva.get_all_children():
		child.docstatus = 0
	nueva.amended_from = original.name
	nueva.set_posting_time = 1
	nueva.posting_date = original.posting_date
	nueva.due_date = original.due_date
	nueva.payment_schedule = []
	for row in nueva.items:
		if row.item_code in items_cuota and _igual(row.rate, anterior):
			row.rate = nuevo
			row.price_list_rate = nuevo
			row.discount_percentage = 0
			row.discount_amount = 0
	nueva.insert(ignore_permissions=True)
	nueva.submit()
	return nueva.name


def run(
	*,
	periodo: str = "10/2026",
	nuevos: dict[str, float] | None = None,
	anteriores: dict[str, float] | None = None,
	apply: bool = False,
	confirm: str = "",
	commit: bool = False,
	report_path: str | None = None,
) -> dict[str, Any]:
	"""Dry-run por defecto; con `apply` enmienda las facturas `a_corregir`."""
	ensure_bulk_apply_allowed(dry_run=not apply, confirm=confirm)
	nuevos = dict(nuevos or CUOTAS_SOCIALES_VIGENTES)
	anteriores = dict(anteriores or CUOTAS_SOCIALES_ANTERIORES)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		frappe.throw("Faltan campos socio / periodo_cobro en Sales Invoice.", frappe.ValidationError)

	items_cuota = _items_cuota_social()
	names = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1, "is_return": 0},
		pluck="name",
		order_by="name asc",
	)
	report: dict[str, Any] = {
		"periodo": periodo,
		"apply": bool(apply),
		"a_corregir": [],
		"corregidas": [],
		"ya_correctas": [],
		"con_pagos": [],
		"revisar": [],
		"sin_cuota": [],
		"errores": [],
	}
	invoices = [frappe.get_doc(SALES_INVOICE_DOCTYPE, n) for n in names]
	socios = {inv.get(campo_socio) for inv in invoices if inv.get(campo_socio)}
	categorias = dict(
		frappe.get_all(
			SOCIO_DOCTYPE,
			filters={"name": ["in", list(socios) or [""]]},
			fields=["name", "categoria"],
			as_list=True,
		)
	)

	for inv in invoices:
		grupo, row = _clasificar(
			inv,
			campo_socio=campo_socio,
			items_cuota=items_cuota,
			categorias=categorias,
			nuevos=nuevos,
			anteriores=anteriores,
		)
		if grupo != "sin_cuota":
			report[grupo].append(row)
		else:
			report["sin_cuota"].append(inv.name)

	if apply:
		for row in report["a_corregir"]:
			try:
				nueva = _enmendar(
					row["factura"],
					items_cuota=items_cuota,
					anterior=row["monto_anterior"],
					nuevo=row["monto_nuevo"],
				)
				sync_saldo_deuda_socio(row["socio"])
				report["corregidas"].append(
					{
						**row,
						"factura_nueva": nueva,
						"grand_total_nuevo": flt(
							frappe.db.get_value(SALES_INVOICE_DOCTYPE, nueva, "grand_total")
						),
					}
				)
				if commit:
					frappe.db.commit()
			except Exception as exc:
				if commit:
					frappe.db.rollback()
				report["errores"].append({**row, "error": str(exc)})
				frappe.log_error(
					title=f"Corrección cuota social {periodo} — {row['factura']}",
					message=frappe.get_traceback(),
				)
				if commit:
					frappe.db.commit()

	report["resumen"] = {
		key: len(report[key])
		for key in ("a_corregir", "corregidas", "ya_correctas", "con_pagos", "revisar", "sin_cuota", "errores")
	}
	report["resumen"]["diferencia_total"] = flt(
		sum(r["grand_total_nuevo"] - r["grand_total"] for r in report["corregidas"])
		if apply
		else sum(
			(r["monto_nuevo"] - r["monto_anterior"])
			for r in report["a_corregir"]
		)
	)
	if report_path:
		with open(report_path, "w", encoding="utf-8") as fh:
			json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
	return report
