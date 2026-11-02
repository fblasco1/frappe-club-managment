"""Parchea SI impagas y cargos Pendiente de CTO COMP Básquet a tarifas de noviembre 2026."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	sync_saldo_deuda_socio,
)
from club_management.ops.consolidate_cuota_social_item import _sync_ple_invoice
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed
from club_management.scripts.informe_concepto_cobranza import (
	ITEM_CUOTA_COMPLEMENTARIA,
	es_cuota_complementaria,
	normalizar_clave_cuota_complementaria,
)

TARIFA_ESC_FEM = 6000.0
TARIFA_RESTO_BASQ = 7000.0
CLAVE_ESC_FEM = "CTO COMP BASQ ESC/FEM"
PERIODO_DEFAULT = "11/2026"


def tarifa_cto_comp_basquet(descripcion_o_titulo: str | None) -> float | None:
	"""Devuelve tarifa nueva si el texto es CTO COMP de básquet; si no, None."""
	if not es_cuota_complementaria(descripcion_o_titulo):
		return None
	clave = normalizar_clave_cuota_complementaria(descripcion_o_titulo)
	if not clave.startswith("CTO COMP BASQ"):
		return None
	# ESC/FEM canónico, alias ESC solo, o FEM sin ESC.
	if CLAVE_ESC_FEM in clave or "ESC/FEM" in clave or " ESC" in clave or clave.endswith(" FEM"):
		return TARIFA_ESC_FEM
	return TARIFA_RESTO_BASQ


def _patch_si_line(row_name: str, tarifa: float) -> None:
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


def _patch_invoice(invoice_name: str, lineas: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
	diff_total = flt(sum(flt(line["diff"]) for line in lineas), 2)
	if abs(diff_total) < 0.005:
		return {"invoice": invoice_name, "action": "sin_cambio", "lineas": lineas}

	old_grand = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "grand_total"))
	old_out = flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "outstanding_amount"))
	new_grand = flt(old_grand + diff_total, 2)
	new_out = flt(max(0.0, old_out + diff_total), 2)
	result: dict[str, Any] = {
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
		_patch_si_line(line["row_name"], flt(line["new_rate"], 2))

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


def _collect_facturas(periodo_cobro: str, *, solo_impagas: bool) -> list[dict[str, Any]]:
	outstanding_clause = "AND si.outstanding_amount > 0.005" if solo_impagas else ""
	rows = frappe.db.sql(
		f"""
		SELECT
			si.name AS invoice,
			si.socio AS socio,
			sii.name AS row_name,
			sii.item_code AS item_code,
			sii.description AS description,
			sii.rate AS rate
		FROM "tabSales Invoice" si
		INNER JOIN "tabSales Invoice Item" sii ON sii.parent = si.name
		WHERE si.docstatus = 1
		  AND COALESCE(si.is_return, 0) = 0
		  AND si.periodo_cobro = %s
		  {outstanding_clause}
		  AND (
			UPPER(COALESCE(sii.description, '')) LIKE '%%CTO COMP%%BAS%%'
			OR sii.item_code = %s
		  )
		ORDER BY si.name, sii.idx
		""",
		(periodo_cobro, ITEM_CUOTA_COMPLEMENTARIA),
		as_dict=True,
	)

	by_invoice: dict[str, dict[str, Any]] = {}
	for row in rows:
		tarifa = tarifa_cto_comp_basquet(row.description)
		if tarifa is None:
			continue
		old_rate = flt(row.rate, 2)
		if abs(old_rate - tarifa) < 0.005:
			continue
		inv = row.invoice
		if inv not in by_invoice:
			by_invoice[inv] = {"invoice": inv, "socio": row.socio or "", "lineas": []}
		by_invoice[inv]["lineas"].append(
			{
				"row_name": row.row_name,
				"description": row.description,
				"clave": normalizar_clave_cuota_complementaria(row.description),
				"old_rate": old_rate,
				"new_rate": tarifa,
				"diff": flt(tarifa - old_rate, 2),
			}
		)
	return list(by_invoice.values())


def _collect_cargos_pendientes() -> list[dict[str, Any]]:
	rows = frappe.get_all(
		"Cargo Socio",
		filters={"estado": "Pendiente"},
		fields=["name", "socio", "titulo", "monto"],
	)
	out: list[dict[str, Any]] = []
	for row in rows:
		tarifa = tarifa_cto_comp_basquet(row.titulo)
		if tarifa is None:
			continue
		old = flt(row.monto, 2)
		if abs(old - tarifa) < 0.005:
			continue
		out.append(
			{
				"cargo": row.name,
				"socio": row.socio,
				"titulo": row.titulo,
				"clave": normalizar_clave_cuota_complementaria(row.titulo),
				"old_monto": old,
				"new_monto": tarifa,
			}
		)
	return out


def run(
	*,
	periodo_cobro: str = PERIODO_DEFAULT,
	solo_impagas: bool = True,
	dry_run: bool = True,
	confirm: str = "",
	limit: int | None = None,
) -> dict[str, Any]:
	"""Alinea CTO COMP Básquet impagas del período + cargos Pendiente a 6000/7000."""
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)

	facturas = _collect_facturas(periodo_cobro, solo_impagas=solo_impagas)
	cargos = _collect_cargos_pendientes()
	if limit:
		facturas = facturas[: int(limit)]
		cargos = cargos[: int(limit)]

	detalles_si: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []
	socios: set[str] = set()
	parcheadas = 0

	for entry in facturas:
		try:
			res = _patch_invoice(entry["invoice"], entry["lineas"], dry_run=dry_run)
			res["socio"] = entry.get("socio") or ""
			detalles_si.append(res)
			if res.get("action") in ("patched", "would_patch"):
				parcheadas += 1
				if res["socio"]:
					socios.add(res["socio"])
		except Exception as exc:
			errores.append({"invoice": entry["invoice"], "error": str(exc)})

	detalles_cargo: list[dict[str, Any]] = []
	cargos_parcheados = 0
	for entry in cargos:
		row = {
			**entry,
			"action": "would_patch" if dry_run else "patched",
		}
		if not dry_run:
			try:
				frappe.db.set_value(
					"Cargo Socio",
					entry["cargo"],
					"monto",
					entry["new_monto"],
					update_modified=True,
				)
				cargos_parcheados += 1
				if entry.get("socio"):
					socios.add(entry["socio"])
			except Exception as exc:
				row["action"] = "error"
				row["error"] = str(exc)
				errores.append({"cargo": entry["cargo"], "error": str(exc)})
				detalles_cargo.append(row)
				continue
		else:
			cargos_parcheados += 1
		detalles_cargo.append(row)

	if not dry_run:
		for socio in socios:
			sync_saldo_deuda_socio(socio)
		if not getattr(frappe.flags, "in_test", False):
			frappe.db.commit()

	return {
		"dry_run": dry_run,
		"periodo_cobro": periodo_cobro,
		"solo_impagas": solo_impagas,
		"tarifas": {
			CLAVE_ESC_FEM: TARIFA_ESC_FEM,
			"CTO COMP BASQ (resto)": TARIFA_RESTO_BASQ,
		},
		"facturas_revisadas": len(facturas),
		"facturas_parcheadas": parcheadas,
		"cargos_revisados": len(cargos),
		"cargos_parcheados": cargos_parcheados,
		"errores": errores[:30],
		"muestra_facturas": detalles_si[:40],
		"muestra_cargos": detalles_cargo[:40],
	}
