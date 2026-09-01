"""Corrige categoría Activo, becas y facturas de socios (carga masiva local)."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from club_management.members.services.cargo_extra_conceptos import item_es_arancel_actividad
from club_management.ops.consolidate_cuota_social_item import _sync_ple_invoice

CUOTA_ITEM = "ICDPE-CUOTA-SOCIAL"
TARIFA_ACTIVO = 31000.0
SOCIO_BECA_ARANCEL = "6864"
BECA_ARANCEL_DESDE = "2026-01-01"
BECA_ARANCEL_HASTA = "2026-08-31"
BECA_TOTAL_DESDE = "2026-09-01"


def _reset_cuota_invoice_totals(name: str, *, rate: float = TARIFA_ACTIVO) -> None:
	"""Restaura totales de cuota tras parches locales erróneos."""
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": name, "item_code": CUOTA_ITEM},
		pluck="name",
	)
	if len(items) != 1:
		return
	row_name = items[0]
	frappe.db.set_value(
		"Sales Invoice Item",
		row_name,
		{
			"rate": rate,
			"price_list_rate": rate,
			"discount_amount": 0,
			"amount": rate,
			"base_rate": rate,
			"base_amount": rate,
			"net_rate": rate,
			"net_amount": rate,
		},
		update_modified=False,
	)
	frappe.db.set_value(
		"Sales Invoice",
		name,
		{
			"grand_total": rate,
			"rounded_total": rate,
			"base_grand_total": rate,
			"total": rate,
			"base_total": rate,
			"net_total": rate,
			"base_net_total": rate,
			"outstanding_amount": rate,
		},
		update_modified=False,
	)
	_sync_ple_invoice(name, rate)


def _patch_cuota_tarifa_invoice(name: str, tarifa: float, *, dry_run: bool) -> dict:
	"""Ajusta línea de cuota a tarifa de categoría; mantiene aranceles y sincroniza PLE."""
	item_rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": name, "item_code": CUOTA_ITEM},
		fields=["name", "rate", "discount_amount"],
	)
	if not item_rows:
		return {"invoice": name, "action": "sin_cuota"}
	old_cuota = flt(item_rows[0].rate)
	if abs(old_cuota - tarifa) < 0.005 and flt(item_rows[0].discount_amount) == 0:
		return {"invoice": name, "action": "sin_cambio"}

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


def _patch_invoice_local(name: str, *, dry_run: bool) -> dict:
	return _patch_cuota_tarifa_invoice(name, TARIFA_ACTIVO, dry_run=dry_run)


def _fix_invoice(name: str, *, dry_run: bool) -> dict:
	return _patch_invoice_local(name, dry_run=dry_run)


def _ensure_beca_arancel_6864(*, dry_run: bool) -> dict:
	socio = SOCIO_BECA_ARANCEL
	existing = frappe.db.exists(
		"Beca Socio",
		{
			"socio": socio,
			"estado": "Activa",
			"tipo_beca": "Parcial Exime Arancel",
			"fecha_desde": ["<=", BECA_ARANCEL_DESDE],
			"fecha_hasta": [">=", BECA_ARANCEL_DESDE],
		},
	)
	if existing:
		return {"socio": socio, "beca": existing, "action": "beca_arancel_ya_existe"}

	payload = {
		"doctype": "Beca Socio",
		"socio": socio,
		"tipo_beca": "Parcial Exime Arancel",
		"fecha_desde": BECA_ARANCEL_DESDE,
		"fecha_hasta": BECA_ARANCEL_HASTA,
		"estado": "Activa",
		"observaciones": "Beca arancel básquet desde inicio 2026 (exime aranceles hasta ago/2026).",
	}
	if dry_run:
		return {"socio": socio, "action": "would_create_beca_arancel", "payload": payload}

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)
	return {"socio": socio, "action": "beca_arancel_creada", "beca": doc.name}


def _waive_arancel_lines_6864(*, dry_run: bool) -> list[dict]:
	"""Anula líneas de arancel impagas ene–ago/2026 (beca exime arancel)."""
	results: list[dict] = []
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={
			"socio": SOCIO_BECA_ARANCEL,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
		},
		fields=["name", "grand_total", "outstanding_amount"],
		order_by="name",
	)
	for inv in invoices:
		items = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": inv.name},
			fields=["name", "item_code", "amount", "rate"],
		)
		arancel_rows = [r for r in items if item_es_arancel_actividad((r.item_code or "").strip())]
		if not arancel_rows:
			continue

		old_total = flt(inv.grand_total)
		new_total = 0.0
		for row in items:
			code = (row.item_code or "").strip()
			if item_es_arancel_actividad(code):
				continue
			new_total += flt(row.amount or row.rate)

		entry = {
			"invoice": inv.name,
			"action": "would_waive_arancel" if dry_run else "waived_arancel",
			"old_total": old_total,
			"new_total": flt(new_total, 2),
			"arancel_items": [r.item_code for r in arancel_rows],
		}
		results.append(entry)
		if dry_run:
			continue

		for row in arancel_rows:
			frappe.db.set_value(
				"Sales Invoice Item",
				row.name,
				{
					"rate": 0,
					"price_list_rate": 0,
					"discount_amount": 0,
					"amount": 0,
					"base_rate": 0,
					"base_amount": 0,
					"net_rate": 0,
					"net_amount": 0,
				},
				update_modified=False,
			)
		new_total = flt(new_total, 2)
		frappe.db.set_value(
			"Sales Invoice",
			inv.name,
			{
				"grand_total": new_total,
				"rounded_total": new_total,
				"base_grand_total": new_total,
				"total": new_total,
				"base_total": new_total,
				"net_total": new_total,
				"base_net_total": new_total,
				"outstanding_amount": new_total,
			},
			update_modified=False,
		)
	return results


def _ensure_beca_total_6864(*, dry_run: bool) -> dict:
	socio = "6864"
	existing = frappe.db.exists(
		"Beca Socio",
		{
			"socio": socio,
			"estado": "Activa",
			"tipo_beca": "Total",
			"fecha_desde": ["<=", "2026-09-01"],
			"fecha_hasta": [">=", "2026-09-01"],
		},
	)
	if existing:
		return {"socio": socio, "beca": existing, "action": "ya_existe"}

	payload = {
		"doctype": "Beca Socio",
		"socio": socio,
		"tipo_beca": "Total",
		"fecha_desde": BECA_TOTAL_DESDE,
		"fecha_hasta": "2026-12-31",
		"estado": "Activa",
		"observaciones": "Beca total desde septiembre 2026 (corrección categoría Activo).",
	}
	if dry_run:
		return {"socio": socio, "action": "would_create_beca", "payload": payload}

	doc = frappe.get_doc(payload)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"socio": socio, "action": "beca_creada", "beca": doc.name}


def run(
	socios: list[str] | None = None,
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar en local.")

	targets = socios or ["10745", "6864"]
	out: dict = {"socios": {}, "dry_run": dry_run}

	for socio in targets:
		cat = frappe.db.get_value("Socio", socio, "categoria")
		if cat != "Activo":
			frappe.db.set_value("Socio", socio, "categoria", "Activo", update_modified=False)
		invoices = frappe.get_all(
			"Sales Invoice",
			filters={
				"socio": socio,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			pluck="name",
			order_by="name",
		)
		invoice_results = []
		for n in invoices:
			invoice_results.append(_fix_invoice(n, dry_run=dry_run))
			if not dry_run and frappe.db.count(
				"Sales Invoice Item", {"parent": n, "item_code": CUOTA_ITEM}
			):
				out = flt(frappe.db.get_value("Sales Invoice", n, "outstanding_amount"))
				if out > TARIFA_ACTIVO + 0.005 or out <= 0:
					_reset_cuota_invoice_totals(n)
					invoice_results.append({"invoice": n, "action": "reset_totals"})
		out["socios"][socio] = {
			"categoria": frappe.db.get_value("Socio", socio, "categoria"),
			"invoices": invoice_results,
		}

	if "6864" in targets:
		out["beca_arancel_6864"] = _ensure_beca_arancel_6864(dry_run=dry_run)
		out["waive_arancel_6864"] = _waive_arancel_lines_6864(dry_run=dry_run)
		out["beca_total_6864"] = _ensure_beca_total_6864(dry_run=dry_run)

	if not dry_run:
		frappe.db.commit()
	return out


SOCIOS_CATEGORIA_ACTIVO = (
	"10736",
	"11322",
	"11786",
	"5637",
	"6141",
	"7563",
	"7869",
	"9073",
)
TARIFA_2_HERMANO = 27500.0
SOCIO_2_HERMANO_SALDO = "12043"
# Informe cobró 32775 (Menor×1,15); exigido correcto 27500×1,15 por 3 cuotas (jun/jul/ago).
SALDO_FAVOR_12043 = 3450.0


def _fix_socio_tarifa_cuota(
	socio: str,
	tarifa: float,
	*,
	categoria: str | None = None,
	dry_run: bool,
) -> dict:
	if categoria and frappe.db.get_value("Socio", socio, "categoria") != categoria:
		if not dry_run:
			frappe.db.set_value("Socio", socio, "categoria", categoria, update_modified=False)
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"socio": socio, "docstatus": 1, "outstanding_amount": [">", 0]},
		pluck="name",
		order_by="name",
	)
	patches = [_patch_cuota_tarifa_invoice(n, tarifa, dry_run=dry_run) for n in invoices]
	return {
		"socio": socio,
		"categoria": categoria or frappe.db.get_value("Socio", socio, "categoria"),
		"tarifa": tarifa,
		"invoices": patches,
	}


def _registrar_saldo_favor_socio(
	socio_name: str,
	monto: float,
	*,
	posting_date: str,
	nota: str,
	dry_run: bool,
) -> dict:
	if monto <= 0:
		return {"socio": socio_name, "action": "skip", "monto": 0}
	if dry_run:
		return {
			"socio": socio_name,
			"action": "would_create_advance_pe",
			"monto": monto,
			"nota": nota,
		}
	from club_management.integrations.payment_ledger_postgres import apply_patch
	from club_management.members.services.cobranza_manual import (
		SALES_INVOICE_DOCTYPE,
		_default_company,
		ensure_customer_for_socio,
	)

	apply_patch()
	ensure_customer_for_socio(socio_name, skip_permission_check=True)
	inv = frappe.db.get_value(
		SALES_INVOICE_DOCTYPE,
		{"socio": socio_name, "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if not inv:
		frappe.throw(f"Sin facturas para registrar saldo a favor de {socio_name}")

	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry(SALES_INVOICE_DOCTYPE, inv, party_amount=flt(monto, 2))
	pe.set("references", [])
	pe.paid_amount = flt(monto, 2)
	pe.received_amount = flt(monto, 2)
	pe.posting_date = posting_date
	pe.reference_date = posting_date
	pe.reference_no = f"SALDO-FAVOR-{socio_name}"[:140]
	pe.remarks = nota
	pe.insert(ignore_permissions=True)
	pe.submit()
	return {"socio": socio_name, "action": "saldo_favor_pe", "monto": monto, "payment_entry": pe.name}


def run_correccion_categorias_lote(
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	"""Corrige socios Activo facturados como Menor + saldo a favor 12043 (2° Hermano)."""
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	out: dict = {"dry_run": dry_run, "activos": [], "segundo_hermano": None}
	for socio in SOCIOS_CATEGORIA_ACTIVO:
		out["activos"].append(
			_fix_socio_tarifa_cuota(
				socio, TARIFA_ACTIVO, categoria="Activo", dry_run=dry_run
			)
		)

	out["segundo_hermano"] = _fix_socio_tarifa_cuota(
		SOCIO_2_HERMANO_SALDO,
		TARIFA_2_HERMANO,
		categoria="2° Hermano",
		dry_run=dry_run,
	)
	out["saldo_favor_12043"] = _registrar_saldo_favor_socio(
		SOCIO_2_HERMANO_SALDO,
		SALDO_FAVOR_12043,
		posting_date="2026-08-25",
		nota=(
			"Saldo a favor: informe cobró cuota Menor con mora ($32.775); "
			"tarifa correcta 2° Hermano $27.500 × 1,15 = $31.625 (jun/jul/ago 2026). "
			"Diferencia $1.150 × 3 = $3.450."
		),
		dry_run=dry_run,
	)

	if not dry_run:
		frappe.db.commit()
	return out


SALDO_PENDIENTE_JULIO = (
	{
		"socio": "11482",
		"invoice": "ACC-SINV-2026-00381",
		"monto": 2000.0,
		"fecha_pago": "2026-08-05",
		"medio_pago": "Wire Transfer",
	},
	{
		"socio": "11512",
		"invoice": "ACC-SINV-2026-00394",
		"monto": 2000.0,
		"fecha_pago": "2026-08-12",
		"medio_pago": "Wire Transfer",
	},
)


def run_saldo_pendiente_julio_11482_11512(
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	"""Aplica pago parcial ($2.000) contra factura jul/2026 (resto cuota mes anterior)."""
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	from club_management.members.services.cobranza_manual import registrar_cobro_parcial_factura

	out: list[dict] = []
	for row in SALDO_PENDIENTE_JULIO:
		if dry_run:
			outstanding = flt(
				frappe.db.get_value("Sales Invoice", row["invoice"], "outstanding_amount")
			)
			out.append(
				{
					**row,
					"action": "would_partial",
					"outstanding_antes": outstanding,
				}
			)
			continue
		result = registrar_cobro_parcial_factura(
			row["socio"],
			row["invoice"],
			row["monto"],
			mode_of_payment=row["medio_pago"],
			posting_date=row["fecha_pago"],
		)
		outstanding_despues = flt(
			frappe.db.get_value("Sales Invoice", row["invoice"], "outstanding_amount")
		)
		out.append(
			{
				**row,
				"action": "partial_applied",
				"payment_entries": result.get("payment_entries"),
				"outstanding_despues": outstanding_despues,
			}
		)

	if not dry_run:
		frappe.db.commit()
	return {"dry_run": dry_run, "pagos": out}


MORA_JUL_15_PCT = 4650.0
SOCIOS_JUL_TARIFA_VIEJA = ("1278", "11788", "12184", "11547")


def _patch_invoice_grand_total(name: str, new_total: float, *, dry_run: bool) -> dict:
	old_grand = flt(frappe.db.get_value("Sales Invoice", name, "grand_total"))
	old_out = flt(frappe.db.get_value("Sales Invoice", name, "outstanding_amount"))
	if abs(old_grand - new_total) < 0.005:
		return {"invoice": name, "action": "sin_cambio", "total": old_grand}
	diff = flt(new_total - old_grand, 2)
	new_out = flt(max(0.0, old_out + diff), 2)
	result = {
		"invoice": name,
		"action": "would_patch_total" if dry_run else "patched_total",
		"old_total": old_grand,
		"new_total": flt(new_total, 2),
		"new_outstanding": new_out,
	}
	if dry_run:
		return result
	for row in frappe.get_all(
		"Sales Invoice Item", filters={"parent": name}, fields=["name", "rate", "amount"]
	):
		frappe.db.set_value(
			"Sales Invoice Item",
			row.name,
			{
				"rate": new_total,
				"price_list_rate": new_total,
				"amount": new_total,
				"base_rate": new_total,
				"base_amount": new_total,
				"net_rate": new_total,
				"net_amount": new_total,
			},
			update_modified=False,
		)
	frappe.db.set_value(
		"Sales Invoice",
		name,
		{
			"grand_total": new_total,
			"rounded_total": new_total,
			"base_grand_total": new_total,
			"total": new_total,
			"base_total": new_total,
			"net_total": new_total,
			"base_net_total": new_total,
			"outstanding_amount": new_out,
		},
		update_modified=False,
	)
	_sync_ple_invoice(name)
	return result


def run_ajuste_jul_activo_tarifa_vieja(
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	"""Jul/2026 facturado a $29.000 + mora $4.350 → tarifa Activo $31.000 + mora $4.650."""
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	out: list[dict] = []
	for socio in SOCIOS_JUL_TARIFA_VIEJA:
		jul = frappe.db.get_value(
			"Sales Invoice",
			{"socio": socio, "periodo_cobro": "07/2026", "docstatus": 1},
			"name",
		)
		mora = frappe.db.get_value(
			"Sales Invoice",
			{"socio": socio, "periodo_cobro": "07/2026-MORA", "docstatus": 1},
			"name",
		)
		entry = {"socio": socio, "julio": None, "mora": None}
		if jul:
			entry["julio"] = _patch_cuota_tarifa_invoice(jul, TARIFA_ACTIVO, dry_run=dry_run)
		if mora:
			entry["mora"] = _patch_invoice_grand_total(mora, MORA_JUL_15_PCT, dry_run=dry_run)
		out.append(entry)

	if not dry_run:
		frappe.db.commit()
	return {"dry_run": dry_run, "socios": out}


def run_realign_ple_jul_activo_35650(
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	"""Corrige PLE (grand_total, no outstanding) en jul/2026 + mora de los 4 socios."""
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	fixed: list[dict] = []
	for socio in SOCIOS_JUL_TARIFA_VIEJA:
		for periodo in ("07/2026", "07/2026-MORA"):
			inv = frappe.db.get_value(
				"Sales Invoice",
				{"socio": socio, "periodo_cobro": periodo, "docstatus": 1},
				"name",
			)
			if not inv:
				continue
			grand = flt(frappe.db.get_value("Sales Invoice", inv, "grand_total"))
			ple_before = frappe.db.sql(
				"""
				SELECT amount_in_account_currency FROM "tabPayment Ledger Entry"
				WHERE voucher_no = %s AND against_voucher_no = %s AND delinked = 0 LIMIT 1
				""",
				(inv, inv),
			)
			ple_amt = flt(ple_before[0][0]) if ple_before else None
			if dry_run:
				fixed.append(
					{
						"invoice": inv,
						"grand_total": grand,
						"ple_before": ple_amt,
						"would_fix": ple_amt is not None and abs(ple_amt - grand) > 0.005,
					}
				)
				continue
			changed = _sync_ple_invoice(inv)
			outstanding = flt(frappe.db.get_value("Sales Invoice", inv, "outstanding_amount"))
			fixed.append(
				{
					"invoice": inv,
					"grand_total": grand,
					"ple_before": ple_amt,
					"ple_synced": changed,
					"outstanding": outstanding,
				}
			)

	if not dry_run:
		frappe.db.commit()
	return {"dry_run": dry_run, "invoices": fixed}


def run_cobro_residual_jul_activo_35650(
	*,
	dry_run: bool = False,
	confirm: str = "",
) -> dict:
	"""Imputa el resto ($2.300) tras parche tarifa jul/2026 para cobros informe $35.650."""
	if not dry_run and confirm != "local-dev":
		frappe.throw("Pase confirm='local-dev' para aplicar.")

	from club_management.members.services.cobranza_manual import registrar_cobro_parcial_factura

	casos = (
		("1278", "ACC-SINV-2026-00805", "ACC-SINV-2026-03686", "2026-08-06", "Wire Transfer"),
		("11788", "ACC-SINV-2026-00483", "ACC-SINV-2026-03687", "2026-08-10", "Wire Transfer"),
		("12184", "ACC-SINV-2026-00749", "ACC-SINV-2026-03688", "2026-08-10", "Cash"),
		("11547", "ACC-SINV-2026-00406", "ACC-SINV-2026-03689", "2026-08-24", "Wire Transfer"),
	)
	out: list[dict] = []
	for socio, jul, mora, fecha, medio in casos:
		if dry_run:
			out.append(
				{
					"socio": socio,
					"jul_out": flt(frappe.db.get_value("Sales Invoice", jul, "outstanding_amount")),
					"mora_out": flt(frappe.db.get_value("Sales Invoice", mora, "outstanding_amount")),
				}
			)
			continue
		pes: list[str] = []
		for inv, take in ((jul, 2000.0), (mora, 300.0)):
			outstanding = flt(frappe.db.get_value("Sales Invoice", inv, "outstanding_amount"))
			if outstanding <= 0.005:
				continue
			amt = min(take, outstanding)
			if amt <= 0.005:
				continue
			result = registrar_cobro_parcial_factura(
				socio,
				inv,
				amt,
				mode_of_payment=medio,
				posting_date=fecha,
				reference_no=f"RES-JUL-35650-{socio}-{inv[-4:]}",
			)
			pes.extend(result.get("payment_entries") or [])
		out.append({"socio": socio, "payment_entries": pes})

	if not dry_run:
		frappe.db.commit()
	return {"dry_run": dry_run, "pagos": out}
