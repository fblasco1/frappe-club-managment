"""Informe de cobranza del día: header (total/medios) + listado por socio + totales por concepto."""

from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)
from club_management.members.services.modos_pago_desk import DESK_MODOS_PAGO_COBRANZA
from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)


def _label_medio(mode: str) -> str:
	for row in DESK_MODOS_PAGO_COBRANZA:
		if row["value"] == mode:
			return _(row["label"])
	return mode


def _fold_sort_key(value: str | None) -> str:
	"""Normaliza texto para orden alfabético (Álvarez antes que Zárate)."""
	text = unicodedata.normalize("NFKD", value or "")
	return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _empty_informe(dia: date) -> dict[str, Any]:
	return {
		"fecha": str(dia),
		"pagos": [],
		"lineas": [],
		"por_medio": [],
		"por_concepto": [],
		"total": 0.0,
	}


def _normalize_concepto(description: str | None, item_code: str | None) -> str:
	raw = (description or item_code or _("Concepto")).strip()
	lower = raw.lower()
	if "cuota social" in lower or lower.startswith("cuota"):
		return _("Cuota Social")
	if "arancel" in lower:
		return raw if raw else _("Arancel actividad")
	return raw or _("Concepto")


def get_informe_pagos_del_dia(fecha: str | date | None = None) -> dict[str, Any]:
	"""Pagos del día: líneas por socio/concepto, totales por medio y por concepto."""
	ensure_secretaria_operacion_access()
	dia = getdate(fecha or today())
	if not erpnext_cobranza_disponible():
		return _empty_informe(dia)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)

	pe_rows = frappe.get_all(
		"Payment Entry",
		filters={"docstatus": 1, "posting_date": dia, "payment_type": "Receive"},
		fields=["name", "posting_date", "mode_of_payment", "paid_amount", "received_amount", "party"],
		order_by="creation asc",
	)
	if not pe_rows:
		return _empty_informe(dia)

	pe_names = [row.name for row in pe_rows]
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"parent": ["in", pe_names],
			"parenttype": "Payment Entry",
			"reference_doctype": SALES_INVOICE_DOCTYPE,
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	refs_by_pe: dict[str, list[Any]] = {}
	invoice_names: set[str] = set()
	for ref in refs:
		refs_by_pe.setdefault(ref.parent, []).append(ref)
		invoice_names.add(ref.reference_name)

	invoice_meta: dict[str, dict[str, Any]] = {}
	if invoice_names:
		fields = ["name", "customer"]
		if campo_socio:
			fields.append(campo_socio)
		for inv in frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={"name": ["in", list(invoice_names)]},
			fields=fields,
		):
			invoice_meta[inv.name] = inv

	lineas_by_inv: dict[str, list[dict[str, Any]]] = {}
	if invoice_names:
		for row in frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": ["in", list(invoice_names)]},
			fields=["parent", "item_code", "description", "amount"],
			order_by="idx asc",
		):
			lineas_by_inv.setdefault(row.parent, []).append(
				{
					"concepto": _normalize_concepto(row.description, row.item_code),
					"amount": flt(row.amount),
				}
			)

	socio_ids = {
		invoice_meta[name].get(campo_socio)
		for name in invoice_names
		if campo_socio and invoice_meta.get(name, {}).get(campo_socio)
	}
	socio_names: dict[str, dict[str, Any]] = {}
	if socio_ids:
		for s in frappe.get_all(
			"Socio",
			filters={"name": ["in", list(socio_ids)]},
			fields=["name", "nombre", "apellido"],
		):
			socio_names[s.name] = s

	pagos: list[dict[str, Any]] = []
	lineas: list[dict[str, Any]] = []
	por_medio: dict[str, float] = {}
	por_concepto: dict[str, float] = {}
	total = 0.0

	def _add_concepto(concepto: str, amount: float) -> None:
		por_concepto[concepto] = por_concepto.get(concepto, 0.0) + flt(amount)

	def _append_linea(
		*,
		socio_id: str | None,
		concepto: str,
		mode: str,
		amount: float,
		payment_entry: str,
		sales_invoice: str,
	) -> None:
		socio = socio_names.get(socio_id or "") or {}
		apellido = (socio.get("apellido") or "").strip()
		nombre = (socio.get("nombre") or "").strip()
		label = f"{apellido}, {nombre}".strip(", ") or (socio_id or "")
		lineas.append(
			{
				"socio": socio_id,
				"apellido": apellido,
				"nombre": nombre,
				"socio_label": label,
				"concepto": concepto,
				"mode_of_payment": mode,
				"paid_amount": flt(amount),
				"payment_entry": payment_entry,
				"sales_invoice": sales_invoice,
			}
		)

	for pe in pe_rows:
		amount = flt(pe.paid_amount or pe.received_amount)
		total += amount
		mode = pe.mode_of_payment or _("Sin medio")
		por_medio[mode] = por_medio.get(mode, 0.0) + amount

		ref_rows = refs_by_pe.get(pe.name, [])
		si_list = [r.reference_name for r in ref_rows]
		socio_name = None
		if campo_socio and si_list:
			socio_name = invoice_meta.get(si_list[0], {}).get(campo_socio)

		pagos.append(
			{
				"payment_entry": pe.name,
				"posting_date": pe.posting_date,
				"mode_of_payment": mode,
				"paid_amount": amount,
				"socio": socio_name,
				"party": pe.party,
				"sales_invoices": si_list,
			}
		)

		for ref in ref_rows:
			allocated = flt(ref.allocated_amount)
			if allocated <= 0:
				continue
			inv_socio = None
			if campo_socio:
				inv_socio = invoice_meta.get(ref.reference_name, {}).get(campo_socio)
			inv_lineas = lineas_by_inv.get(ref.reference_name) or []
			line_total = sum(flt(l["amount"]) for l in inv_lineas)
			if not inv_lineas or line_total <= 0:
				concepto = _("Sin concepto")
				_add_concepto(concepto, allocated)
				_append_linea(
					socio_id=inv_socio,
					concepto=concepto,
					mode=mode,
					amount=allocated,
					payment_entry=pe.name,
					sales_invoice=ref.reference_name,
				)
				continue
			if len(inv_lineas) == 1:
				concepto = inv_lineas[0]["concepto"]
				_add_concepto(concepto, allocated)
				_append_linea(
					socio_id=inv_socio,
					concepto=concepto,
					mode=mode,
					amount=allocated,
					payment_entry=pe.name,
					sales_invoice=ref.reference_name,
				)
				continue
			acumulado = 0.0
			for idx, linea in enumerate(inv_lineas):
				if idx == len(inv_lineas) - 1:
					parte = flt(allocated - acumulado)
				else:
					parte = flt(allocated * (flt(linea["amount"]) / line_total))
					acumulado += parte
				concepto = linea["concepto"]
				_add_concepto(concepto, parte)
				_append_linea(
					socio_id=inv_socio,
					concepto=concepto,
					mode=mode,
					amount=parte,
					payment_entry=pe.name,
					sales_invoice=ref.reference_name,
				)

	lineas.sort(
		key=lambda row: (
			_fold_sort_key(row.get("apellido")),
			_fold_sort_key(row.get("nombre")),
			_fold_sort_key(row.get("concepto")),
			row.get("payment_entry") or "",
		)
	)

	# Orden de totales: Cuota Social primero, luego el resto alfabético
	def _concepto_sort_key(name: str) -> tuple[int, str]:
		if name == _("Cuota Social") or name.lower() == "cuota social":
			return (0, name.lower())
		return (1, name.lower())

	return {
		"fecha": str(dia),
		"pagos": pagos,
		"lineas": lineas,
		"por_medio": [
			{"mode_of_payment": k, "total": flt(v)} for k, v in sorted(por_medio.items())
		],
		"por_concepto": [
			{"concepto": k, "total": flt(v)}
			for k, v in sorted(por_concepto.items(), key=lambda item: _concepto_sort_key(item[0]))
		],
		"total": flt(total),
	}


def get_pagos_del_dia_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Socio"), "fieldname": "socio_label", "fieldtype": "Data", "width": 220},
		{"label": _("Concepto"), "fieldname": "concepto", "fieldtype": "Data", "width": 180},
		{"label": _("Medio de pago"), "fieldname": "mode_of_payment", "fieldtype": "Data", "width": 130},
		{"label": _("Monto"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{
			"label": _("Payment Entry"),
			"fieldname": "payment_entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 140,
		},
	]


def get_pagos_del_dia_report_data(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	informe = get_informe_pagos_del_dia((filters or {}).get("fecha") or today())
	rows: list[dict[str, Any]] = []
	for linea in informe["lineas"]:
		rows.append(
			{
				"socio": linea.get("socio"),
				"socio_label": linea.get("socio_label"),
				"concepto": linea.get("concepto"),
				"mode_of_payment": _label_medio(str(linea.get("mode_of_payment") or "")),
				"paid_amount": linea.get("paid_amount"),
				"payment_entry": linea.get("payment_entry"),
			}
		)

	if informe["por_concepto"]:
		rows.append(
			{
				"socio_label": "",
				"concepto": _("— Totales por concepto —"),
				"mode_of_payment": "",
				"paid_amount": None,
				"payment_entry": "",
			}
		)
		for row in informe["por_concepto"]:
			rows.append(
				{
					"socio_label": "",
					"concepto": _("Total {0}").format(row["concepto"]),
					"mode_of_payment": "",
					"paid_amount": row["total"],
					"payment_entry": "",
				}
			)
	return rows


def get_pagos_del_dia_report_summary(filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	"""Header: solo total recaudado + desglose por medio de pago."""
	informe = get_informe_pagos_del_dia((filters or {}).get("fecha") or today())
	summary: list[dict[str, Any]] = [
		{"value": informe["total"], "label": _("Total recaudado"), "datatype": "Currency"},
	]
	for row in informe["por_medio"]:
		summary.append(
			{
				"value": row["total"],
				"label": _label_medio(row["mode_of_payment"]),
				"datatype": "Currency",
			}
		)
	return summary
