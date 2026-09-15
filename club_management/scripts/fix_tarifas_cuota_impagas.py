"""Parchea facturas impagas de cuota social a tarifa vigente por categoría del socio."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	resolve_cuota_social,
)
from club_management.ops.consolidate_cuota_social_item import (
	CANONICAL_ITEM,
	_sync_ple_invoice,
)
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed

TARIFAS_VIGENTES: dict[str, float] = {
	"Activo": 31000.0,
	"Menor": 28500.0,
	"2° Hermano": 27500.0,
	"3° Hermano": 23500.0,
	"Adherente": 19500.0,
	"Jubilado": 5500.0,
}


def _patch_cuota_tarifa_invoice(name: str, tarifa: float, *, dry_run: bool) -> dict:
	item_rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": name, "item_code": CANONICAL_ITEM},
		fields=["name", "rate"],
	)
	if not item_rows:
		return {"invoice": name, "action": "sin_cuota"}
	old_cuota = flt(item_rows[0].rate)
	if abs(old_cuota - tarifa) < 0.005:
		return {"invoice": name, "action": "sin_cambio", "rate": old_cuota}

	old_grand = flt(frappe.db.get_value("Sales Invoice", name, "grand_total"))
	old_out = flt(frappe.db.get_value("Sales Invoice", name, "outstanding_amount"))
	diff = flt(tarifa - old_cuota, 2)
	new_grand = flt(old_grand + diff, 2)
	new_out = flt(max(0.0, old_out + diff), 2)
	result = {
		"invoice": name,
		"action": "would_patch" if dry_run else "patched",
		"old_cuota": old_cuota,
		"new_cuota": tarifa,
		"old_total": old_grand,
		"new_total": new_grand,
		"new_outstanding": new_out,
	}
	if dry_run:
		return result

	for row in item_rows:
		frappe.db.set_value(
			"Sales Invoice Item",
			row.name,
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
	frappe.db.set_value(
		"Sales Invoice",
		name,
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
	_sync_ple_invoice(name)
	return result


def run(
	*,
	dry_run: bool = False,
	confirm: str = "",
	limit: int | None = None,
) -> dict:
	"""Alinea líneas ICDPE-CUOTA-SOCIAL impagas a resolve_cuota_social del socio."""
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw("Sales Invoice sin campo socio")

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT si.name AS invoice, si.socio AS socio
		FROM "tabSales Invoice" si
		INNER JOIN "tabSales Invoice Item" sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND si.outstanding_amount > 0
		  AND sii.item_code = %s
		ORDER BY si.name
		""",
		(CANONICAL_ITEM,),
		as_dict=True,
	)
	if limit:
		rows = rows[: int(limit)]

	patched = 0
	sin_cambio = 0
	detalles: list[dict] = []
	errores: list[dict] = []

	for row in rows:
		socio = row.socio
		inv = row.invoice
		try:
			tarifa, _item = resolve_cuota_social(socio)
			tarifa = flt(tarifa, 2)
			if tarifa <= 0:
				continue
			categoria = frappe.db.get_value("Socio", socio, "categoria")
			res = _patch_cuota_tarifa_invoice(inv, tarifa, dry_run=dry_run)
			res["socio"] = socio
			res["categoria"] = categoria
			detalles.append(res)
			if res.get("action") == "patched":
				patched += 1
			elif res.get("action") in ("sin_cambio", "would_patch"):
				if res.get("action") == "sin_cambio":
					sin_cambio += 1
				elif res.get("action") == "would_patch":
					patched += 1
		except Exception as exc:
			errores.append({"invoice": inv, "socio": socio, "error": str(exc)})

	if not dry_run:
		frappe.db.commit()

	return {
		"dry_run": dry_run,
		"revisadas": len(rows),
		"parcheadas": patched,
		"sin_cambio": sin_cambio,
		"errores": errores[:20],
		"muestra": detalles[:30],
		"tarifas_vigentes": TARIFAS_VIGENTES,
	}
