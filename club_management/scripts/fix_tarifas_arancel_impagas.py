"""Parchea facturas impagas de aranceles a tarifa vigente del catálogo (Item Price / standard_rate)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.activities.data.patin_aranceles_icdpe import PATIN_ITEM_SPECS
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	sync_saldo_deuda_socio,
)
from club_management.ops.consolidate_cuota_social_item import _sync_ple_invoice
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed


def _tarifa_vigente_item(item_code: str) -> float:
	return flt(
		frappe.db.get_value("Item Price", {"item_code": item_code}, "price_list_rate")
		or frappe.db.get_value("Item", item_code, "standard_rate")
		or 0,
		2,
	)


def _patch_arancel_line(row_name: str, tarifa: float, *, dry_run: bool) -> None:
	if dry_run:
		return
	frappe.db.set_value(
		"Sales Invoice Item",
		row_name,
		{
			"rate": tarifa,
			"price_list_rate": tarifa,
			"discount_amount": 0,
			"amount": tarifa,
			"base_rate": tarifa,
			"base_amount": tarifa,
			"net_rate": tarifa,
			"net_amount": tarifa,
		},
		update_modified=False,
	)


def _patch_invoice_aranceles(
	invoice_name: str,
	lineas: list[dict],
	*,
	dry_run: bool,
) -> dict:
	if not lineas:
		return {"invoice": invoice_name, "action": "sin_cambio"}

	diff_total = flt(sum(flt(line["diff"]) for line in lineas), 2)
	if abs(diff_total) < 0.005:
		return {"invoice": invoice_name, "action": "sin_cambio"}

	old_grand = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "grand_total"))
	old_out = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
	new_grand = flt(old_grand + diff_total, 2)
	new_out = flt(max(0.0, old_out + diff_total), 2)

	result = {
		"invoice": invoice_name,
		"action": "would_patch" if dry_run else "patched",
		"lineas": lineas,
		"diff_total": diff_total,
		"old_total": old_grand,
		"new_total": new_grand,
		"new_outstanding": new_out,
	}
	if dry_run:
		return result

	for line in lineas:
		_patch_arancel_line(line["row_name"], flt(line["new_rate"], 2), dry_run=False)

	frappe.db.set_value(
		SALES_INVOICE_DOCTYPE,
		invoice_name,
		{
			"grand_total": new_grand,
			"rounded_total": new_grand,
			"base_grand_total": new_grand,
			"total": new_grand,
			"base_total": new_grand,
			"net_total": new_grand,
			"base_net_total": new_grand,
			"outstanding_amount": new_out,
		},
		update_modified=False,
	)
	_sync_ple_invoice(invoice_name, new_grand)
	return result


def run(
	*,
	periodo_cobro: str = "09/2026",
	item_codes: list[str] | None = None,
	item_prefix: str = "",
	solo_impagas: bool = True,
	dry_run: bool = False,
	confirm: str = "",
	limit: int | None = None,
) -> dict:
	"""Alinea líneas de arancel impagas al precio vigente del ítem en catálogo."""
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)

	codes = list(item_codes or [])
	if not codes and item_prefix:
		codes = frappe.get_all("Item", filters={"item_code": ["like", f"{item_prefix}%"]}, pluck="name")
	if not codes:
		frappe.throw("Indicá item_codes o item_prefix")

	placeholders = ", ".join(["%s"] * len(codes))
	outstanding_clause = "AND si.outstanding_amount > 0" if solo_impagas else ""

	rows = frappe.db.sql(
		f"""
		SELECT
			si.name AS invoice,
			si.socio AS socio,
			sii.name AS row_name,
			sii.item_code AS item_code,
			sii.rate AS rate
		FROM "tabSales Invoice" si
		INNER JOIN "tabSales Invoice Item" sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND si.periodo_cobro = %s
		  {outstanding_clause}
		  AND sii.item_code IN ({placeholders})
		ORDER BY si.name, sii.idx
		""",
		(periodo_cobro, *codes),
		as_dict=True,
	)

	by_invoice: dict[str, dict] = {}
	for row in rows:
		tarifa = _tarifa_vigente_item(row.item_code)
		if tarifa <= 0:
			continue
		old_rate = flt(row.rate, 2)
		if abs(old_rate - tarifa) < 0.005:
			continue
		diff = flt(tarifa - old_rate, 2)
		inv = row.invoice
		if inv not in by_invoice:
			by_invoice[inv] = {"invoice": inv, "socio": row.socio, "lineas": []}
		by_invoice[inv]["lineas"].append(
			{
				"row_name": row.row_name,
				"item_code": row.item_code,
				"old_rate": old_rate,
				"new_rate": tarifa,
				"diff": diff,
			}
		)

	invoices = list(by_invoice.values())
	if limit:
		invoices = invoices[: int(limit)]

	patched = 0
	sin_cambio = 0
	detalles: list[dict] = []
	errores: list[dict] = []
	socios_afectados: set[str] = set()

	for entry in invoices:
		inv = entry["invoice"]
		socio = entry.get("socio") or ""
		try:
			res = _patch_invoice_aranceles(inv, entry["lineas"], dry_run=dry_run)
			res["socio"] = socio
			detalles.append(res)
			action = res.get("action")
			if action in ("patched", "would_patch"):
				patched += 1
				if socio:
					socios_afectados.add(socio)
			elif action == "sin_cambio":
				sin_cambio += 1
		except Exception as exc:
			errores.append({"invoice": inv, "socio": socio, "error": str(exc)})

	if not dry_run:
		for socio in socios_afectados:
			sync_saldo_deuda_socio(socio)
		frappe.db.commit()

	tarifas = {code: _tarifa_vigente_item(code) for code in codes}

	return {
		"dry_run": dry_run,
		"periodo_cobro": periodo_cobro,
		"item_codes": codes,
		"solo_impagas": solo_impagas,
		"revisadas": len(invoices),
		"parcheadas": patched,
		"sin_cambio": sin_cambio,
		"errores": errores[:20],
		"muestra": detalles[:30],
		"tarifas_vigentes": tarifas,
	}


def run_patin_septiembre(
	*,
	periodo_cobro: str = "09/2026",
	dry_run: bool = False,
	confirm: str = "",
	limit: int | None = None,
) -> dict:
	"""Atajo: alinea aranceles ICDPE-PATIN-* del período al catálogo vigente."""
	return run(
		periodo_cobro=periodo_cobro,
		item_codes=[spec.item_code for spec in PATIN_ITEM_SPECS],
		solo_impagas=True,
		dry_run=dry_run,
		confirm=confirm,
		limit=limit,
	)
