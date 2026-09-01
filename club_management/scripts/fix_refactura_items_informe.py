"""Refactura líneas de Sales Invoice según concepto del informe (local ops)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.scripts.bulk_io import ensure_bulk_apply_allowed

from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	ITEM_BOXEO_2_CLASES,
	ITEM_BOXEO_3_CLASES,
	ITEM_GIMNASIA_1_CLASE,
	ITEM_GIMNASIA_2_CLASES,
)
from club_management.activities.data.basquet_aranceles_icdpe import ITEM_MINIBASQUET
from club_management.members.services.cobranza_manual import SALES_INVOICE_DOCTYPE
from club_management.ops.consolidate_cuota_social_item import _sync_ple_invoice

ITEM_ESCUELITA = "ICDPE-BASQUET-ESCUELITA"

REFACTURAS_LOTE: tuple[dict[str, str | float], ...] = (
	# Gimnasia artística: informe «GIMNASIA ARTISTICA» = 2 clases
	{"socio": "11462", "periodo": "08/2026", "from_item": ITEM_GIMNASIA_1_CLASE, "to_item": ITEM_GIMNASIA_2_CLASES},
	{"socio": "12042", "periodo": "08/2026", "from_item": ITEM_GIMNASIA_1_CLASE, "to_item": ITEM_GIMNASIA_2_CLASES},
	{"socio": "12043", "periodo": "08/2026", "from_item": ITEM_GIMNASIA_1_CLASE, "to_item": ITEM_GIMNASIA_2_CLASES},
	{"socio": "9577", "periodo": "08/2026", "from_item": ITEM_GIMNASIA_1_CLASE, "to_item": ITEM_GIMNASIA_2_CLASES},
	# Pre-Mini B U9 → minibasquet (no escuelita)
	{"socio": "10249", "periodo": "08/2026", "from_item": ITEM_ESCUELITA, "to_item": ITEM_MINIBASQUET},
	{"socio": "11989", "periodo": "08/2026", "from_item": ITEM_ESCUELITA, "to_item": ITEM_MINIBASQUET},
)


def _tarifa_item(item_code: str) -> float:
	return flt(frappe.db.get_value("Item", item_code, "standard_rate"), 2)


def _factura_socio_periodo(socio: str, periodo: str) -> list[str]:
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"socio": socio, "periodo_cobro": periodo, "docstatus": 1},
		pluck="name",
		order_by="name asc",
	)


def refactura_item_en_factura(
	invoice_name: str,
	from_item: str,
	to_item: str,
	*,
	new_rate: float | None = None,
	dry_run: bool = False,
) -> dict:
	"""Cambia item_code y tarifa de una línea; ajusta totales y PLE."""
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name, "item_code": from_item},
		fields=["name", "rate", "amount"],
	)
	if not rows:
		return {"invoice": invoice_name, "action": "sin_linea", "from_item": from_item}
	if len(rows) > 1:
		return {"invoice": invoice_name, "action": "multiples_lineas", "from_item": from_item}

	row = rows[0]
	old_rate = flt(row.rate, 2)
	tarifa = flt(new_rate if new_rate is not None else _tarifa_item(to_item), 2)
	if tarifa <= 0:
		frappe.throw(f"Sin tarifa para {to_item}")

	diff = flt(tarifa - old_rate, 2)
	old_grand = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "grand_total"))
	old_out = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
	new_grand = flt(old_grand + diff, 2)
	new_out = flt(max(0.0, old_out + diff), 2)

	result = {
		"invoice": invoice_name,
		"action": "would_patch" if dry_run else "patched",
		"from_item": from_item,
		"to_item": to_item,
		"old_rate": old_rate,
		"new_rate": tarifa,
		"old_total": old_grand,
		"new_total": new_grand,
		"new_outstanding": new_out,
	}
	if dry_run:
		return result

	item_name = frappe.db.get_value("Item", to_item, "item_name") or to_item
	frappe.db.set_value(
		"Sales Invoice Item",
		row.name,
		{
			"item_code": to_item,
			"item_name": item_name,
			"description": item_name,
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


def _cancelar_payment_entry(name: str, *, dry_run: bool) -> dict:
	if dry_run:
		return {"payment_entry": name, "action": "would_cancel"}
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	pe = frappe.get_doc("Payment Entry", name)
	if pe.docstatus != 1:
		return {"payment_entry": name, "action": "skip", "docstatus": pe.docstatus}
	pe.cancel()
	return {"payment_entry": name, "action": "cancelled"}


def fix_socio_11844_boxeo(*, dry_run: bool = False) -> dict:
	"""Revierte cobro erróneo 2 clases y refactura a BOXEO 3 clases."""
	invoice = "ACC-SINV-2026-02276"
	pes = ("ACC-PAY-2026-02166", "ACC-PAY-2026-02168")
	out: dict = {"invoice": invoice, "payment_entries": [], "refactura": None}
	for pe_name in pes:
		out["payment_entries"].append(_cancelar_payment_entry(pe_name, dry_run=dry_run))
	if not dry_run:
		frappe.db.set_value(
			SALES_INVOICE_DOCTYPE,
			invoice,
			{"outstanding_amount": flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice, "grand_total"))},
			update_modified=False,
		)
	out["refactura"] = refactura_item_en_factura(
		invoice,
		ITEM_BOXEO_2_CLASES,
		ITEM_BOXEO_3_CLASES,
		dry_run=dry_run,
	)
	return out


def run_refactura_lote(*, dry_run: bool = False, confirm: str = "") -> dict:
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)

	from club_management.integrations.payment_ledger_postgres import apply_patch

	if not dry_run:
		apply_patch()

	detalles: list[dict] = []
	for spec in REFACTURAS_LOTE:
		socio = str(spec["socio"])
		periodo = str(spec["periodo"])
		from_item = str(spec["from_item"])
		to_item = str(spec["to_item"])
		for inv in _factura_socio_periodo(socio, periodo):
			rows = frappe.get_all(
				"Sales Invoice Item",
				filters={"parent": inv, "item_code": from_item},
				pluck="name",
			)
			if not rows:
				continue
			res = refactura_item_en_factura(inv, from_item, to_item, dry_run=dry_run)
			res["socio"] = socio
			res["periodo"] = periodo
			detalles.append(res)

	boxeo = fix_socio_11844_boxeo(dry_run=dry_run)

	if not dry_run:
		frappe.db.commit()

	return {
		"dry_run": dry_run,
		"refacturas": detalles,
		"boxeo_11844": boxeo,
		"parcheadas": sum(1 for d in detalles if d.get("action") == "patched"),
	}


def run(*, dry_run: bool = True, confirm: str = "") -> dict:
	return run_refactura_lote(dry_run=dry_run, confirm=confirm)
