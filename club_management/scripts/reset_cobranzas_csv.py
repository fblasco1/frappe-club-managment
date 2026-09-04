"""Reset limpio de cobranzas del CSV: inventario y cancelación.

Spec: `club_management/specs/reset_cobranzas_csv.md`

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.reset_cobranzas_csv.run_prod_inventario
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
)
from club_management.scripts.bulk_io import (
	CONFIRM_LOCAL,
	cell,
	find_socio,
	is_production_site,
	parse_monto,
	read_bulk_rows,
)
from club_management.scripts.informe_concepto_cobranza import (
	es_concepto_carnet,
	periodo_es_adelantado,
	TARIFAS_PATIN_AGOSTO_2026,
)

CONFIRM_RESET_PROD = "RESET_PROD"


def _ensure_reset_allowed(*, dry_run: bool, confirm: str) -> None:
	if dry_run:
		return
	token = (confirm or "").strip()
	if is_production_site():
		if token != CONFIRM_RESET_PROD:
			frappe.throw(
				_("Reset bloqueado en {0}. confirm='{1}'.").format(
					frappe.local.site, CONFIRM_RESET_PROD
				),
				frappe.ValidationError,
			)
		return
	if token != CONFIRM_LOCAL:
		frappe.throw(
			_("Reset bloqueado en {0}. confirm='{1}'.").format(frappe.local.site, CONFIRM_LOCAL),
			frappe.ValidationError,
		)


def _filas_csv(csv_path: str) -> list[dict[str, str]]:
	"""Filas con nro, socio, periodo, concepto, monto."""
	out: list[dict[str, str]] = []
	for idx, raw in enumerate(read_bulk_rows(csv_path), start=2):
		nro = cell(raw, "nro_socio", "numero_socio", "nro")
		periodo = cell(raw, "periodo", "periodo_cobro")
		dni = cell(raw, "dni")
		concepto = cell(raw, "concepto")
		socio = find_socio(nro_socio=nro, dni=dni) or ""
		out.append(
			{
				"fila": str(idx),
				"nro_socio": nro,
				"socio": socio,
				"periodo": periodo,
				"concepto": concepto,
				"monto_csv": str(parse_monto(cell(raw, "monto_abonado", "monto"))),
			}
		)
	return out


def _si_es_carnet(invoice_name: str) -> bool:
	descs = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name},
		pluck="description",
	)
	if not descs:
		return False
	return all(es_concepto_carnet(d) or "CARNET" in (d or "").upper() for d in descs)


def _periodo_de(invoice_name: str, campo_periodo: str | None) -> str:
	if not campo_periodo:
		return ""
	return str(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, campo_periodo) or "").strip()


def _si_socio_periodo(socio_name: str, periodo: str) -> list[str]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo or not socio_name or not periodo:
		return []
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_socio: socio_name, campo_periodo: periodo, "docstatus": 1},
		pluck="name",
	)


def _si_periodo(periodo: str) -> list[str]:
	campo_periodo = _campo_periodo_cobro()
	if not campo_periodo or not periodo:
		return []
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1},
		pluck="name",
	)


def _pes_imputados(invoice_names: set[str]) -> list[str]:
	if not invoice_names:
		return []
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", list(invoice_names)],
			"parenttype": "Payment Entry",
		},
		pluck="parent",
	)
	return list(dict.fromkeys(refs))


def _mora_vinculadas(invoice_names: set[str]) -> list[str]:
	found: list[str] = []
	for name in invoice_names:
		found.extend(
			frappe.get_all(
				SALES_INVOICE_DOCTYPE,
				filters={"docstatus": 1, "remarks": ["like", f"%Mora al cobro {name}%"]},
				pluck="name",
			)
		)
	return list(dict.fromkeys(found))


def _pes_inf_en_rango(fecha_desde: str, fecha_hasta: str) -> list[str]:
	return frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": ["in", [0, 1]],
			"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
			"reference_no": ["like", "INF-%"],
		},
		pluck="name",
	)


def _socio_de_pe(pe_name: str) -> str:
	customer = frappe.db.get_value("Payment Entry", pe_name, "party")
	campo_cust = _campo_socio_en("Customer")
	if not customer or not campo_cust:
		return ""
	return str(frappe.db.get_value("Customer", customer, campo_cust) or "")


def inventario(
	*,
	csv_path: str,
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	periodo_cierre: str = "08/2026",
	incluir_todo_periodo_cierre: bool = True,
) -> dict[str, Any]:
	"""Lista SI y PE a cancelar; no persiste."""
	campo_periodo = _campo_periodo_cobro()
	filas = _filas_csv(csv_path)
	carnet_log = [f for f in filas if es_concepto_carnet(f["concepto"])]
	sin_socio = [
		f
		for f in filas
		if not f["socio"] and not es_concepto_carnet(f["concepto"])
	]
	adelantado_csv = [
		f
		for f in filas
		if periodo_es_adelantado(f["periodo"], periodo_cierre)
		and not es_concepto_carnet(f["concepto"])
	]
	pares = [
		f
		for f in filas
		if not es_concepto_carnet(f["concepto"])
		and not periodo_es_adelantado(f["periodo"], periodo_cierre)
	]
	socios_csv = {f["socio"] for f in pares if f["socio"]}
	socios_inf = socios_csv | {f["socio"] for f in adelantado_csv if f["socio"]}
	si: set[str] = set()
	si_adelantadas: set[str] = set()
	if incluir_todo_periodo_cierre:
		si.update(n for n in _si_periodo(periodo_cierre) if not _si_es_carnet(n))
	else:
		for socio in socios_csv:
			si.update(n for n in _si_socio_periodo(socio, periodo_cierre) if not _si_es_carnet(n))

	for fila in pares:
		socio = fila["socio"]
		periodo = fila["periodo"]
		if not socio or not periodo:
			continue
		si.update(n for n in _si_socio_periodo(socio, periodo) if not _si_es_carnet(n))

	for pe_name in _pes_inf_en_rango(fecha_desde, fecha_hasta):
		if not incluir_todo_periodo_cierre and (
			not socios_inf or _socio_de_pe(pe_name) not in socios_inf
		):
			continue
		ref_no = str(frappe.db.get_value("Payment Entry", pe_name, "reference_no") or "")
		if es_concepto_carnet(ref_no) or "-CARNET" in ref_no.upper():
			continue
		for ref in frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": pe_name, "reference_doctype": SALES_INVOICE_DOCTYPE},
			pluck="reference_name",
		):
			if frappe.db.get_value(SALES_INVOICE_DOCTYPE, ref, "docstatus") != 1:
				continue
			if _si_es_carnet(ref):
				continue
			periodo = _periodo_de(ref, campo_periodo)
			if periodo_es_adelantado(periodo, periodo_cierre):
				si.add(ref)
				si_adelantadas.add(ref)
			elif not periodo_es_adelantado(periodo, periodo_cierre):
				si.add(ref)

	mora = set(_mora_vinculadas(si))
	si |= mora

	pes = set(_pes_imputados(si))
	for pe_name in _pes_inf_en_rango(fecha_desde, fecha_hasta):
		if incluir_todo_periodo_cierre or (
			socios_inf and _socio_de_pe(pe_name) in socios_inf
		):
			pes.add(pe_name)
	pes_filtrados: list[str] = []
	for pe_name in pes:
		ref_no = str(frappe.db.get_value("Payment Entry", pe_name, "reference_no") or "")
		if es_concepto_carnet(ref_no) or "-CARNET" in ref_no.upper():
			continue
		refs = frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": pe_name, "reference_doctype": SALES_INVOICE_DOCTYPE},
			pluck="reference_name",
		)
		if not refs:
			pes_filtrados.append(pe_name)
			continue
		# PE solo contra SI futura: entra al reset (adelantado), no se reimputa.
		pes_filtrados.append(pe_name)

	por_periodo: dict[str, int] = defaultdict(int)
	for name in si:
		por_periodo[_periodo_de(name, campo_periodo) or "(sin período)"] += 1

	si_mora = sorted(mora)
	si_resto = sorted(si - mora)
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	for name in si:
		per = _periodo_de(name, campo_periodo)
		if periodo_es_adelantado(per, periodo_cierre):
			si_adelantadas.add(name)
	adelantado_si_log: list[dict[str, str]] = []
	for name in sorted(si_adelantadas):
		socio = ""
		if campo_socio:
			socio = str(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, campo_socio) or "")
		pes_si = _pes_imputados({name})
		adelantado_si_log.append(
			{
				"motivo": "excluido_adelantado",
				"fila": "",
				"nro_socio": socio,
				"socio": socio,
				"periodo": _periodo_de(name, campo_periodo),
				"concepto": "",
				"monto_csv": str(
					flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "grand_total") or 0)
				),
				"sales_invoice": name,
				"payment_entry": ";".join(pes_si),
			}
		)

	def _rev(motivo: str, fila: dict[str, str]) -> dict[str, str]:
		return {
			"motivo": motivo,
			"fila": fila.get("fila") or "",
			"nro_socio": fila.get("nro_socio") or "",
			"socio": fila.get("socio") or "",
			"periodo": fila.get("periodo") or "",
			"concepto": fila.get("concepto") or "",
			"monto_csv": fila.get("monto_csv") or "",
			"sales_invoice": "",
			"payment_entry": "",
		}

	revision_manual = (
		[_rev("excluido_carnet", f) for f in carnet_log]
		+ [_rev("error_socio_no_encontrado", f) for f in sin_socio]
		+ [_rev("excluido_adelantado", f) for f in adelantado_csv]
		+ adelantado_si_log
	)
	return {
		"csv_path": csv_path,
		"fecha_desde": fecha_desde,
		"fecha_hasta": fecha_hasta,
		"periodo_cierre": periodo_cierre,
		"filas_csv": len(filas),
		"sales_invoices": si_mora + si_resto,
		"sales_invoices_mora": si_mora,
		"payment_entries": sorted(set(pes_filtrados)),
		"conteo_si_por_periodo": dict(por_periodo),
		"carnet": {
			"filas": len(carnet_log),
			"monto": flt(sum(flt(f["monto_csv"]) for f in carnet_log), 2),
			"detalle": carnet_log,
		},
		"revision_manual": revision_manual,
	}


def _cancelar_doc(doctype: str, name: str) -> str:
	status = frappe.db.get_value(doctype, name, "docstatus")
	if status == 2:
		return "ya_cancelado"
	doc = frappe.get_doc(doctype, name)
	doc.flags.ignore_permissions = True
	if status == 0:
		doc.delete(ignore_permissions=True)
		return "eliminado_draft"
	doc.cancel()
	return "cancelado"


def _aplicar_cancelacion(inv: dict[str, Any], *, commit_every: int = 25) -> dict[str, Any]:
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	in_test = bool(getattr(frappe.flags, "in_test", False))
	frappe.flags.mute_emails = True
	pe_ok = 0
	pe_err: list[str] = []
	hechos = 0

	def _commit_lote() -> None:
		if in_test or not commit_every or hechos % commit_every != 0:
			return
		frappe.db.commit()
		print(f"  lote {hechos}: PE ok={pe_ok} err={len(pe_err)}")

	for name in inv["payment_entries"]:
		try:
			_cancelar_doc("Payment Entry", name)
			pe_ok += 1
		except Exception as exc:
			if not in_test:
				frappe.db.rollback()
			pe_err.append(f"{name}: {exc}")
		hechos += 1
		_commit_lote()
	si_ok = 0
	si_err: list[str] = []
	for name in inv["sales_invoices"]:
		try:
			_cancelar_doc(SALES_INVOICE_DOCTYPE, name)
			si_ok += 1
		except Exception as exc:
			if not in_test:
				frappe.db.rollback()
			si_err.append(f"{name}: {exc}")
		hechos += 1
		if not in_test and commit_every and hechos % commit_every == 0:
			frappe.db.commit()
			print(f"  lote {hechos}: SI ok={si_ok} err={len(si_err)}")
	if not in_test:
		frappe.db.commit()
	return {
		"pe_cancelados": pe_ok,
		"si_canceladas": si_ok,
		"errores_pe": pe_err[:200],
		"errores_pe_total": len(pe_err),
		"errores_si": si_err[:200],
		"errores_si_total": len(si_err),
	}


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	confirm: str = "",
	fase: str = "inventario",
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	periodo_cierre: str = "08/2026",
	out_path: str | None = None,
	incluir_todo_periodo_cierre: bool = True,
) -> dict[str, Any]:
	"""Inventario o cancelación del universo del CSV. No refactura ni aplica cobros."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_reset_allowed(dry_run=dry_run, confirm=confirm)
	inv = inventario(
		csv_path=csv_path,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		periodo_cierre=periodo_cierre,
		incluir_todo_periodo_cierre=incluir_todo_periodo_cierre,
	)
	inv["dry_run"] = dry_run
	inv["fase"] = fase
	if not dry_run and fase == "cancelar":
		inv["aplicacion"] = _aplicar_cancelacion(inv)
	destino = Path(out_path or f"{csv_path}.reset_inventario.json")
	rev_path = Path(f"{csv_path}.revision_manual.csv")
	rev_rows = inv.get("revision_manual") or []
	with rev_path.open("w", encoding="utf-8", newline="") as handle:
		fields = [
			"motivo",
			"fila",
			"nro_socio",
			"socio",
			"periodo",
			"concepto",
			"monto_csv",
			"sales_invoice",
			"payment_entry",
		]
		writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
		writer.writeheader()
		writer.writerows(rev_rows)
	inv["revision_manual_path"] = str(rev_path)
	destino.write_text(json.dumps(inv, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
	inv["out_path"] = str(destino)
	print(
		f"reset cobranzas fase={fase} dry_run={dry_run} "
		f"SI={len(inv['sales_invoices'])} PE={len(inv['payment_entries'])} "
		f"periodos={inv['conteo_si_por_periodo']}"
	)
	from collections import Counter

	rev = inv.get("revision_manual") or []
	if rev:
		print(f" revisión Secretaría: {len(rev)} filas → {inv.get('revision_manual_path')}")
		for motivo, cant in sorted(Counter(r.get("motivo") for r in rev).items()):
			print(f"   {motivo}: {cant}")
	if not dry_run and fase == "cancelar":
		print(
			" aplicación: PE={pe_cancelados} SI={si_canceladas} "
			"err_pe={errores_pe_total} err_si={errores_si_total}".format(
				**inv["aplicacion"]
			)
		)
	return inv


def run_prod_inventario() -> dict[str, Any]:
	return run(csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv", dry_run=True)


def cancelar_prod_agosto() -> dict[str, Any]:
	"""Apply de cancelación en producción. No imprime el inventario completo."""
	result = run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=False,
		confirm=CONFIRM_RESET_PROD,
		fase="cancelar",
	)
	slim = {
		"dry_run": False,
		"fase": "cancelar",
		"si_en_inventario": len(result.get("sales_invoices") or []),
		"pe_en_inventario": len(result.get("payment_entries") or []),
		"conteo_si_por_periodo": result.get("conteo_si_por_periodo"),
		"aplicacion": result.get("aplicacion"),
		"revision_manual_path": result.get("revision_manual_path"),
		"out_path": result.get("out_path"),
	}
	print(json.dumps(slim, indent=2, ensure_ascii=False, default=str))
	return slim
