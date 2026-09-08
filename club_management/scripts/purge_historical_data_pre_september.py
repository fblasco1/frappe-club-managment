"""Purga y migración histórica con cutoff 31/08/2026.

Spec: `club_management/specs/purga_migracion_historica_pre_septiembre.md`

    # Dry-run
    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.purge_historical_data_pre_september.run \\
        --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": true}'

    # Apply producción (atómico)
    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.purge_historical_data_pre_september.run \\
        --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv", "dry_run": false, "confirm": "PURGE_MIGRATE_PROD"}'
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	erpnext_cobranza_disponible,
	get_club_settings,
	reference_date_desde_periodo,
	resolve_cost_center_item,
)
from club_management.members.services.cobranza_periodica import primer_vencimiento
from club_management.scripts.bulk_io import (
	CONFIRM_LOCAL,
	cell,
	find_socio,
	is_production_site,
	parse_fecha,
	parse_monto,
	read_bulk_rows,
)
from club_management.scripts.bulk_payments import (
	_registrar_cobro_concepto_informe,
	_registrar_saldo_favor_cliente,
	map_medio_pago,
)
from club_management.scripts.cobranzas_bulk_importer import (
	_mora_pct_esperado,
	_rate_factura_concepto,
)
from club_management.scripts.informe_concepto_cobranza import (
	ITEM_CUOTA_COMPLEMENTARIA,
	buscar_linea_factura_concepto,
	es_concepto_carnet,
	es_cuota_complementaria,
	orden_periodo,
	periodo_es_adelantado,
	referencia_informe,
	resolver_item_codes_concepto,
)

CUTOFF = date(2026, 8, 31)
SEPT_START = date(2026, 9, 1)
PERIODO_CIERRE = "08/2026"
EXPECTED_FILAS = 2562
EXPECTED_TOTAL = 52_115_308.00
CONFIRM_PURGE_PROD = "PURGE_MIGRATE_PROD"


def _ensure_purge_allowed(*, dry_run: bool, confirm: str) -> None:
	if dry_run:
		return
	token = (confirm or "").strip()
	if is_production_site():
		if token != CONFIRM_PURGE_PROD:
			frappe.throw(
				_("Purga/migración bloqueada en {0}. confirm='{1}'.").format(
					frappe.local.site, CONFIRM_PURGE_PROD
				),
				frappe.ValidationError,
			)
		return
	if token != CONFIRM_LOCAL:
		frappe.throw(
			_("Purga/migración bloqueada en {0}. confirm='{1}'.").format(
				frappe.local.site, CONFIRM_LOCAL
			),
			frappe.ValidationError,
		)


def periodo_leq(periodo: str | None, tope: str) -> bool:
	"""True si periodo <= tope (MM/YYYY)."""
	actual = orden_periodo(periodo)
	limite = orden_periodo(tope)
	if not actual or not limite:
		return False
	return actual <= limite


def snapshot_septiembre() -> dict[str, int]:
	"""Conteos de SI/PE de septiembre de producción (excluye SI de mora al cobro).

	Las SI de ajuste `Mora al cobro …` pueden postearse el día del cobro; en
	migración histórica no deben contaminar el invariante de septiembre.
	"""
	si_names = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"posting_date": [">=", SEPT_START], "docstatus": ["in", [0, 1]]},
		fields=["name", "remarks"],
	)
	si = sum(
		1
		for row in si_names
		if "Mora al cobro" not in (row.remarks or "")
	)
	pe = frappe.db.count(
		"Payment Entry",
		{"posting_date": [">=", SEPT_START], "docstatus": ["in", [0, 1]]},
	)
	return {"sept_si_count": int(si), "sept_pe_count": int(pe)}


def assert_septiembre_intacto(antes: dict[str, int]) -> dict[str, int]:
	despues = snapshot_septiembre()
	if despues != antes:
		frappe.throw(
			_("Integridad de septiembre rota: antes={0} después={1}.").format(antes, despues),
			frappe.ValidationError,
		)
	return despues


def _posting_of(doctype: str, name: str) -> date | None:
	raw = frappe.db.get_value(doctype, name, "posting_date")
	return getdate(raw) if raw else None


def assert_pre_september(doctype: str, name: str) -> date:
	"""Safety guard: aborta si el doc es de septiembre en adelante."""
	posting = _posting_of(doctype, name)
	if posting is None:
		frappe.throw(
			_("Safety guard: {0} {1} sin posting_date.").format(doctype, name),
			frappe.ValidationError,
		)
	if posting >= SEPT_START:
		frappe.throw(
			_(
				"Safety guard: intento de tocar {0} {1} con posting_date={2} (>= {3})."
			).format(doctype, name, posting, SEPT_START),
			frappe.ValidationError,
		)
	return posting


def _assert_universo_pre_septiembre(doctype: str, names: list[str]) -> None:
	"""Safety guard en bloque: ningún name con posting_date >= SEPT_START."""
	if not names:
		return
	chunk = 500
	for i in range(0, len(names), chunk):
		parte = names[i : i + chunk]
		violacion = frappe.get_all(
			doctype,
			filters={"name": ["in", parte], "posting_date": [">=", SEPT_START]},
			fields=["name", "posting_date"],
			limit=1,
		)
		if violacion:
			frappe.throw(
				_(
					"Safety guard: intento de tocar {0} {1} con posting_date={2} (>= {3})."
				).format(doctype, violacion[0].name, violacion[0].posting_date, SEPT_START),
				frappe.ValidationError,
			)


def inventariar_purga(
	*,
	cutoff: date = CUTOFF,
	solo_pe: list[str] | None = None,
	solo_si: list[str] | None = None,
	periodo_cierre: str = PERIODO_CIERRE,
) -> dict[str, Any]:
	"""Lista PE y SI a cancelar con posting_date <= cutoff.

	`solo_pe` / `solo_si`: acota el universo (tests / corridas quirúrgicas).
	Sin ellos, toma docs del site con fecha <= cutoff, **excluyendo** SI cuyo
	`periodo_cobro` sea posterior al cierre (p. ej. cuota 09/2026 emitida con
	posting_date 31/08).
	"""
	from club_management.members.services.cobranza_manual import _campo_periodo_cobro

	pe_filters: dict[str, Any] = {
		"docstatus": ["in", [0, 1]],
		"posting_date": ["<=", cutoff],
	}
	si_filters: dict[str, Any] = {
		"docstatus": ["in", [0, 1]],
		"posting_date": ["<=", cutoff],
	}
	if solo_pe is not None:
		pe_filters["name"] = ["in", list(solo_pe) or ["__none__"]]
	if solo_si is not None:
		si_filters["name"] = ["in", list(solo_si) or ["__none__"]]

	pes = frappe.get_all(
		"Payment Entry",
		filters=pe_filters,
		pluck="name",
		order_by="posting_date asc, name asc",
	)
	sis = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=si_filters,
		pluck="name",
		order_by="posting_date asc, name asc",
	)

	campo_periodo = _campo_periodo_cobro()
	si_filtradas: list[str] = []
	si_protegidas = 0
	for name in sis:
		if campo_periodo:
			periodo = str(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, campo_periodo) or "")
			# Cuota/arancel 09/2026+ (aunque posting_date sea 31/08) no se toca.
			if periodo_es_adelantado(periodo, periodo_cierre):
				si_protegidas += 1
				continue
		si_filtradas.append(name)

	_assert_universo_pre_septiembre("Payment Entry", list(pes))
	_assert_universo_pre_septiembre(SALES_INVOICE_DOCTYPE, si_filtradas)
	return {
		"cutoff": str(cutoff),
		"payment_entries": list(pes),
		"sales_invoices": si_filtradas,
		"pe_count": len(pes),
		"si_count": len(si_filtradas),
		"si_protegidas_periodo_futuro": si_protegidas,
	}


def _cancelar_doc(doctype: str, name: str) -> str:
	assert_pre_september(doctype, name)
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


def purgar(
	*,
	inventario: dict[str, Any],
	commit_every: int = 25,
) -> dict[str, Any]:
	"""Cancela PE y luego SI del inventario."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	frappe.flags.mute_emails = True
	in_test = bool(getattr(frappe.flags, "in_test", False))
	pe_ok = 0
	pe_err: list[str] = []
	hechos = 0

	def _maybe_commit() -> None:
		nonlocal hechos
		if in_test or not commit_every:
			return
		if hechos and hechos % commit_every == 0:
			frappe.db.commit()
			print(f"  purga lote={hechos} pe_ok={pe_ok} pe_err={len(pe_err)}")

	for name in inventario["payment_entries"]:
		try:
			_cancelar_doc("Payment Entry", name)
			pe_ok += 1
		except Exception as exc:  # noqa: BLE001
			if not in_test:
				frappe.db.rollback()
			pe_err.append(f"{name}: {exc}")
		hechos += 1
		_maybe_commit()

	si_ok = 0
	si_err: list[str] = []
	for name in inventario["sales_invoices"]:
		try:
			_cancelar_doc(SALES_INVOICE_DOCTYPE, name)
			si_ok += 1
		except Exception as exc:  # noqa: BLE001
			if not in_test:
				frappe.db.rollback()
			si_err.append(f"{name}: {exc}")
		hechos += 1
		_maybe_commit()

	if not in_test and commit_every:
		frappe.db.commit()
	print(f"  purga fin: PE={pe_ok}/{len(inventario['payment_entries'])} SI={si_ok}/{len(inventario['sales_invoices'])}")
	return {
		"pe_cancelados": pe_ok,
		"si_canceladas": si_ok,
		"errores_pe": pe_err[:100],
		"errores_pe_total": len(pe_err),
		"errores_si": si_err[:100],
		"errores_si_total": len(si_err),
	}



def _filas_csv(csv_path: str) -> list[dict[str, Any]]:
	out: list[dict[str, Any]] = []
	for idx, raw in enumerate(read_bulk_rows(csv_path), start=2):
		nro = cell(raw, "nro_socio", "numero_socio", "nro")
		dni = cell(raw, "dni")
		periodo = cell(raw, "periodo", "periodo_cobro")
		concepto = cell(raw, "concepto")
		monto = parse_monto(cell(raw, "monto_abonado", "monto"))
		fecha = parse_fecha(cell(raw, "fecha_pago", "fecha"))
		medio = cell(raw, "medio_pago", "medio")
		ref = cell(raw, "referencia_comprobante", "referencia", "comprobante")
		socio = find_socio(nro_socio=nro, dni=dni) or ""
		out.append(
			{
				"fila": idx,
				"nro_socio": nro,
				"dni": dni,
				"socio": socio,
				"periodo": periodo,
				"concepto": concepto,
				"monto_csv": flt(monto, 2),
				"fecha_pago": fecha,
				"medio_pago": medio,
				"referencia_csv": ref,
				"raw": raw,
			}
		)
	return out


def combos_a_facturar(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Combos únicos (socio, concepto, periodo) con periodo <= 08/2026."""
	seen: set[tuple[str, str, str]] = set()
	combos: list[dict[str, Any]] = []
	for f in filas:
		if es_concepto_carnet(f["concepto"]):
			continue
		if not periodo_leq(f["periodo"], PERIODO_CIERRE):
			continue
		if not f["socio"]:
			continue
		clave = (f["socio"], (f["concepto"] or "").strip(), (f["periodo"] or "").strip())
		if clave in seen:
			continue
		seen.add(clave)
		combos.append(
			{
				"socio": f["socio"],
				"nro_socio": f["nro_socio"],
				"concepto": f["concepto"],
				"periodo": f["periodo"],
				"monto_csv": f["monto_csv"],
				"fecha_pago": f["fecha_pago"],
			}
		)
	return combos


def fechas_factura_historica(periodo: str) -> tuple[date, date]:
	"""Día 1 / día 10 del período — sin forzar a `today()` (migración histórica)."""
	ref = reference_date_desde_periodo(periodo)
	dia = int(get_club_settings().dia_primer_vencimiento or 10)
	due = primer_vencimiento(ref, dia)
	return ref, due


def _emitir_factura_historica(
	socio_name: str,
	periodo: str,
	concepto: str,
	item_code: str,
	*,
	monto: float,
	mora_pct: float,
	_intentos: int = 5,
) -> str:
	"""SI histórica con posting_date = día 1 del período (set_posting_time)."""
	from club_management.integrations.payment_ledger_postgres import apply_patch
	from club_management.members.services.cobranza_manual import _campo_periodo_cobro

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Sales Invoice sin campo de socio configurado."), frappe.ValidationError)
	customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
	posting, due = fechas_factura_historica(periodo)
	rate = _rate_factura_concepto(item_code, periodo, monto_csv=monto, mora_pct=mora_pct)
	linea: dict[str, Any] = {
		"item_code": item_code,
		"qty": 1,
		"rate": rate,
		"description": f"{concepto} ({periodo})",
	}
	company = _default_company()
	cost_center = resolve_cost_center_item(item_code, company)
	if cost_center:
		linea["cost_center"] = cost_center

	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": customer,
		"company": company,
		"posting_date": posting,
		"due_date": due,
		"set_posting_time": 1,
		campo_socio: socio_name,
		"remarks": _("{0} — {1}").format(concepto, periodo),
		"items": [linea],
	}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		payload[campo_periodo] = periodo

	apply_patch()
	last_exc: Exception | None = None
	for intento in range(1, _intentos + 1):
		try:
			invoice = frappe.get_doc(payload)
			invoice.insert(ignore_permissions=True)
			invoice.submit()
			return invoice.name
		except Exception as exc:  # noqa: BLE001 — retry naming series concurrente
			last_exc = exc
			msg = str(exc).lower()
			if "could not serialize" in msg or "concurrent update" in msg:
				frappe.db.rollback()
				continue
			raise
	assert last_exc is not None
	raise last_exc


def emitir_facturas_historicas(
	combos: list[dict[str, Any]],
	*,
	dry_run: bool,
	commit_every: int = 25,
) -> dict[str, Any]:
	"""Emite SI abiertas día 1 / venc día 10 por combo."""
	creadas: list[dict[str, Any]] = []
	omitidas: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []
	in_test = bool(getattr(frappe.flags, "in_test", False))

	for i, combo in enumerate(combos, start=1):
		socio = combo["socio"]
		periodo = combo["periodo"]
		concepto = combo["concepto"]
		monto = flt(combo["monto_csv"], 2)
		fecha = combo.get("fecha_pago") or CUTOFF
		mora_pct = _mora_pct_esperado(periodo, fecha)

		existente = buscar_linea_factura_concepto(
			socio,
			periodo,
			concepto,
			monto_abonado=monto,
			reservadas=set(),
			solo_impagas=False,
		)
		if existente:
			omitidas.append({**combo, "sales_invoice": existente[0], "motivo": "ya_existe"})
			continue

		item_codes = resolver_item_codes_concepto(
			concepto, socio_name=socio, monto_abonado=monto
		)
		es_cto = es_cuota_complementaria(concepto)
		if not item_codes and not es_cto:
			errores.append({**combo, "motivo": "error_concepto_sin_mapeo"})
			continue

		if dry_run:
			item = item_codes[0] if item_codes else ITEM_CUOTA_COMPLEMENTARIA
			rate = _rate_factura_concepto(item, periodo, monto_csv=monto, mora_pct=mora_pct)
			posting, due = fechas_factura_historica(periodo)
			creadas.append(
				{
					**combo,
					"sales_invoice": "",
					"item_code": item,
					"rate": rate,
					"posting_date": str(posting),
					"due_date": str(due),
				}
			)
			continue

		try:
			# CTO COMP: nunca vía prepago/`resolve_fechas_factura_mensual`
			# (fuerza today() en deuda vieja). Misma SI histórica día 1.
			if es_cto:
				item = ITEM_CUOTA_COMPLEMENTARIA
				name = _emitir_factura_historica(
					socio,
					periodo,
					concepto,
					item,
					monto=monto,
					mora_pct=0.0,
				)
			else:
				item = item_codes[0]
				name = _emitir_factura_historica(
					socio,
					periodo,
					concepto,
					item,
					monto=monto,
					mora_pct=mora_pct,
				)
			if not name:
				errores.append({**combo, "motivo": "error_facturacion"})
				continue
			posting = _posting_of(SALES_INVOICE_DOCTYPE, name)
			if posting and posting >= SEPT_START:
				frappe.throw(
					_(
						"Factura histórica {0} quedó con posting_date={1}; abortando."
					).format(name, posting),
					frappe.ValidationError,
				)
			creadas.append({**combo, "sales_invoice": name, "item_code": item})
			if commit_every and not in_test and len(creadas) % commit_every == 0:
				frappe.db.commit()
				print(f"  facturas creadas={len(creadas)}/{len(combos)}")
		except Exception as exc:  # noqa: BLE001
			if not in_test:
				frappe.db.rollback()
			errores.append({**combo, "motivo": str(exc)[:280]})

	if not dry_run and commit_every and not in_test:
		frappe.db.commit()
	print(
		f"  facturas fin: creadas={len(creadas)} omitidas={len(omitidas)} errores={len(errores)}"
	)
	return {
		"creadas": creadas if dry_run else [{"sales_invoice": c.get("sales_invoice"), "periodo": c.get("periodo"), "concepto": c.get("concepto"), "socio": c.get("socio")} for c in creadas],
		"omitidas": omitidas if dry_run else [],
		"errores": errores,
		"creadas_count": len(creadas),
		"omitidas_count": len(omitidas),
		"errores_count": len(errores),
	}


def _monto_base_factura(invoice_name: str, item_code: str) -> float:
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_name, "item_code": item_code},
		fields=["amount", "net_amount", "rate", "qty"],
	)
	if not rows:
		rows = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": invoice_name},
			fields=["amount", "net_amount", "rate", "qty"],
		)
	if not rows:
		return flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, "grand_total") or 0, 2)
	row = rows[0]
	return flt(row.get("amount") or row.get("net_amount") or (flt(row.rate) * flt(row.qty)), 2)


def procesar_cobranzas(
	filas: list[dict[str, Any]],
	*,
	dry_run: bool,
	commit_every: int = 25,
) -> list[dict[str, Any]]:
	"""Ingesta e imputación / anticipos del CSV de agosto."""
	registros: list[dict[str, Any]] = []
	in_test = bool(getattr(frappe.flags, "in_test", False))
	aplicados = 0
	for f in filas:
		reg: dict[str, Any] = {
			"fila": f["fila"],
			"nro_socio": f["nro_socio"],
			"socio": f["socio"],
			"periodo": f["periodo"],
			"concepto": f["concepto"],
			"monto_csv": f["monto_csv"],
			"fecha_pago": f["fecha_pago"].isoformat() if f["fecha_pago"] else "",
			"estado": "",
			"sales_invoice": "",
			"payment_entry": "",
			"monto_base": 0.0,
			"monto_mora": 0.0,
			"monto_imputado": 0.0,
			"mensaje": "",
		}

		def terminar(estado: str, mensaje: str = "") -> dict[str, Any]:
			reg["estado"] = estado
			if mensaje:
				reg["mensaje"] = mensaje
			registros.append(reg)
			return reg

		if es_concepto_carnet(f["concepto"]):
			terminar("excluido_carnet", "CARNET fuera de imputación")
			continue
		if not f["socio"]:
			terminar("error_socio_no_encontrado")
			continue
		if not f["fecha_pago"]:
			terminar("error_fecha_invalida")
			continue
		medio = map_medio_pago(f["medio_pago"])
		if not medio:
			terminar("error_medio_pago_invalido", f["medio_pago"])
			continue
		if f["monto_csv"] <= 0:
			terminar("error_monto_invalido")
			continue

		ref = referencia_informe(
			fila=f["fila"],
			numero_socio=f["nro_socio"] or f["socio"],
			periodo=f["periodo"],
			monto=f["monto_csv"],
			concepto=f["concepto"],
		)

		if periodo_es_adelantado(f["periodo"], PERIODO_CIERRE):
			reg["monto_imputado"] = flt(f["monto_csv"], 2)
			if dry_run:
				terminar("anticipo", "dry-run: PE anticipo no aplicado")
				continue
			try:
				pe_name = _registrar_saldo_favor_cliente(
					f["socio"],
					flt(f["monto_csv"], 2),
					mode_of_payment=medio,
					posting_date=f["fecha_pago"],
					reference_no=ref[:140],
					nota=_("Anticipo migración histórica período {0}").format(f["periodo"]),
				)
			except Exception as exc:  # noqa: BLE001
				if not in_test:
					frappe.db.rollback()
				terminar("error_cobro", str(exc)[:280])
				continue
			reg["payment_entry"] = pe_name
			terminar("anticipo")
			aplicados += 1
			if commit_every and not in_test and aplicados % commit_every == 0:
				frappe.db.commit()
				print(f"  cobros aplicados={aplicados} fila={f['fila']}")
			continue

		if not periodo_leq(f["periodo"], PERIODO_CIERRE):
			terminar("error_periodo", f["periodo"])
			continue

		match = buscar_linea_factura_concepto(
			f["socio"],
			f["periodo"],
			f["concepto"],
			monto_abonado=f["monto_csv"],
			reservadas=set(),
			solo_impagas=True,
		)
		if not match:
			match = buscar_linea_factura_concepto(
				f["socio"],
				f["periodo"],
				f["concepto"],
				monto_abonado=f["monto_csv"],
				reservadas=set(),
				solo_impagas=False,
			)
		if not match:
			terminar("error_sin_factura")
			continue

		invoice_name, item_code, _line = match
		reg["sales_invoice"] = invoice_name
		monto_base = _monto_base_factura(invoice_name, item_code)
		reg["monto_base"] = monto_base
		mora = max(0.0, flt(f["monto_csv"] - monto_base, 2))
		reg["monto_mora"] = mora
		reg["monto_imputado"] = flt(f["monto_csv"], 2)

		if dry_run:
			msg = (
				f"dry-run: imputar base {monto_base} + mora {mora}"
				if mora > 0.005
				else f"dry-run: imputar {flt(f['monto_csv'], 2)}"
			)
			terminar("imputado", msg)
			continue

		try:
			result = _registrar_cobro_concepto_informe(
				f["socio"],
				invoice_name,
				flt(f["monto_csv"], 2),
				mode_of_payment=medio,
				posting_date=f["fecha_pago"],
				reference_no=ref,
				auto_submit=True,
				concepto=f["concepto"],
				periodo_fila=f["periodo"],
			)
		except Exception as exc:  # noqa: BLE001
			if not in_test:
				frappe.db.rollback()
			terminar("error_cobro", str(exc)[:280])
			continue

		pes = result.get("payment_entries") or []
		reg["payment_entry"] = ";".join(pes)
		terminar("imputado")
		aplicados += 1
		if commit_every and not in_test and aplicados % commit_every == 0:
			frappe.db.commit()
			print(f"  cobros aplicados={aplicados} fila={f['fila']}")

	if not dry_run and commit_every and not in_test:
		frappe.db.commit()
	print(f"  cobros fin: aplicados={aplicados} log={len(registros)}")
	return registros


def _validar_totales_csv(filas: list[dict[str, Any]], registros: list[dict[str, Any]]) -> None:
	if len(filas) != EXPECTED_FILAS:
		frappe.throw(
			_("Filas CSV={0}, se esperaban {1}.").format(len(filas), EXPECTED_FILAS),
			frappe.ValidationError,
		)
	total = flt(sum(flt(f["monto_csv"]) for f in filas), 2)
	if abs(total - EXPECTED_TOTAL) > 0.009:
		frappe.throw(
			_("Total CSV={0}, se esperaba {1}.").format(total, EXPECTED_TOTAL),
			frappe.ValidationError,
		)
	if len(registros) != len(filas):
		frappe.throw(
			_("Invariante no-pérdida: log={0} csv={1}.").format(len(registros), len(filas)),
			frappe.ValidationError,
		)
	total_log = flt(sum(flt(r["monto_csv"]) for r in registros), 2)
	if abs(total_log - EXPECTED_TOTAL) > 0.009:
		frappe.throw(
			_("Total log={0}, se esperaba {1}.").format(total_log, EXPECTED_TOTAL),
			frappe.ValidationError,
		)


def _imprimir_control(result: dict[str, Any]) -> None:
	print("\n" + "=" * 72)
	print("CONTROL — Purga / migración histórica pre-septiembre")
	print("=" * 72)
	print(f"  Filas procesadas:     {result.get('filas')}")
	print(f"  Total dinero agosto:  $ {result.get('total_agosto'):,.2f}")
	print(
		f"  Septiembre SI/PE:     {result.get('sept_si_count')} / {result.get('sept_pe_count')} "
		f"(intactos={result.get('septiembre_ok')})"
	)
	estados = result.get("estados") or {}
	if estados:
		print("  Estados:")
		for k, v in sorted(estados.items()):
			print(f"    {k}: {v}")
	purga = result.get("purga") or {}
	if purga:
		print(
			f"  Purga: PE={purga.get('pe_cancelados', purga.get('pe_count'))} "
			f"SI={purga.get('si_canceladas', purga.get('si_count'))}"
		)
	fact = result.get("facturacion") or {}
	if fact:
		print(
			f"  Facturas: creadas={fact.get('creadas_count')} "
			f"omitidas={fact.get('omitidas_count')} errores={fact.get('errores_count')}"
		)
	print("=" * 72)


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	confirm: str = "",
	skip_purge: bool = False,
	skip_facturas: bool = False,
	skip_cobros: bool = False,
	out_path: str | None = None,
	enforce_csv_totales: bool | None = None,
	solo_pe: list[str] | None = None,
	solo_si: list[str] | None = None,
	commit_every: int = 25,
) -> dict[str, Any]:
	"""Purga (<=31/08) + facturas históricas + cobros agosto.

	`enforce_csv_totales`: por defecto True solo si el CSV tiene exactamente
	EXPECTED_FILAS (archivo de producción). En tests con CSV chico queda False.

	`solo_pe` / `solo_si`: acotan la purga (tests); en producción omitirlos.
	`commit_every`: commits por lote (0 = una sola transacción; no recomendado
	en corridas grandes).
	"""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	frappe.flags.mute_emails = True
	in_test = bool(getattr(frappe.flags, "in_test", False))

	sept_antes = snapshot_septiembre()
	filas = _filas_csv(csv_path)
	if enforce_csv_totales is None:
		enforce_csv_totales = len(filas) == EXPECTED_FILAS

	inventario = inventariar_purga(solo_pe=solo_pe, solo_si=solo_si)
	combos = combos_a_facturar(filas)

	result: dict[str, Any] = {
		"csv_path": csv_path,
		"dry_run": dry_run,
		"cutoff": str(CUTOFF),
		"sept_antes": sept_antes,
		"sept_si_count": sept_antes["sept_si_count"],
		"sept_pe_count": sept_antes["sept_pe_count"],
		"filas": len(filas),
		"total_agosto": flt(sum(flt(f["monto_csv"]) for f in filas), 2),
		"purga": {
			"pe_count": inventario["pe_count"],
			"si_count": inventario["si_count"],
			"payment_entries": inventario["payment_entries"] if dry_run else [],
			"sales_invoices": inventario["sales_invoices"] if dry_run else [],
		},
		"combos_facturar": len(combos),
	}

	if enforce_csv_totales:
		_validar_totales_csv(filas, [{"monto_csv": f["monto_csv"]} for f in filas])

	registros: list[dict[str, Any]] = []
	try:
		if not dry_run and not skip_purge:
			print(
				f"==> Purga PE={inventario['pe_count']} SI={inventario['si_count']} "
				f"(commit_every={commit_every})"
			)
			aplicacion = purgar(inventario=inventario, commit_every=commit_every)
			result["purga_aplicacion"] = aplicacion
			result["purga"]["pe_cancelados"] = aplicacion["pe_cancelados"]
			result["purga"]["si_canceladas"] = aplicacion["si_canceladas"]

		if not skip_facturas:
			print(f"==> Facturas históricas combos={len(combos)}")
			# Tras purga, rearmar combos: las SI viejas ya no existen
			result["facturacion"] = emitir_facturas_historicas(
				combos, dry_run=dry_run, commit_every=commit_every
			)

		if not skip_cobros:
			print(f"==> Cobros filas={len(filas)}")
			registros = procesar_cobranzas(
				filas, dry_run=dry_run, commit_every=commit_every
			)
			result["registros"] = len(registros)
			result["estados"] = dict(Counter(r["estado"] for r in registros))
			if enforce_csv_totales:
				_validar_totales_csv(filas, registros)

		sept_despues = assert_septiembre_intacto(sept_antes)
		result["sept_despues"] = sept_despues
		result["septiembre_ok"] = True

		if not dry_run and not in_test:
			frappe.db.commit()
	except Exception:
		if not dry_run and not in_test and not commit_every:
			frappe.db.rollback()
		result["septiembre_ok"] = False
		raise

	# Slim result for disk: drop huge name lists
	slim = {k: v for k, v in result.items()}
	if slim.get("purga"):
		slim["purga"] = {
			k: v
			for k, v in slim["purga"].items()
			if k not in ("payment_entries", "sales_invoices")
		}

	destino = Path(out_path or f"{csv_path}.purga_migracion.json")
	destino.write_text(
		json.dumps(slim, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
	)
	result["out_path"] = str(destino)
	if registros:
		aud = Path(f"{csv_path}.purga_migracion.auditoria.json")
		aud.write_text(
			json.dumps(registros, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
		)
		result["auditoria_path"] = str(aud)

	_imprimir_control(result)
	return result


def _pe_existe_para_fila(f: dict[str, Any]) -> bool:
	"""True si ya hay PE submitted con la referencia canónica INF de la fila."""
	ref = referencia_informe(
		fila=f["fila"],
		numero_socio=f["nro_socio"] or f["socio"],
		periodo=f["periodo"],
		monto=f["monto_csv"],
		concepto=f["concepto"],
	)
	if frappe.db.exists("Payment Entry", {"reference_no": ref[:140], "docstatus": 1}):
		return True
	rows = frappe.db.sql(
		"""
		select name from `tabPayment Entry`
		where docstatus = 1 and reference_no like %s
		limit 1
		""",
		(f"%fila {f['fila']}%",),
	)
	return bool(rows)


def inventariar_filas_sin_pe(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Filas imputables (≤08/2026) sin PE — las ~623 del apply local."""
	out: list[dict[str, Any]] = []
	for f in filas:
		if es_concepto_carnet(f["concepto"]):
			continue
		if not f["socio"]:
			continue
		if periodo_es_adelantado(f["periodo"], PERIODO_CIERRE):
			continue
		if not periodo_leq(f["periodo"], PERIODO_CIERRE):
			continue
		if _pe_existe_para_fila(f):
			continue
		out.append(f)
	return out


def retry_sin_pe(
	*,
	csv_path: str,
	dry_run: bool = True,
	confirm: str = "",
	commit_every: int = 25,
	out_path: str | None = None,
) -> dict[str, Any]:
	"""Emite SI faltantes (CTO vía histórica) e imputa cobros de filas sin PE.

	No purga. Respeta integridad de septiembre (mora SI/PE = fecha_pago).
	"""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	frappe.flags.mute_emails = True
	in_test = bool(getattr(frappe.flags, "in_test", False))
	sept_antes = snapshot_septiembre()
	filas = _filas_csv(csv_path)
	pendientes = inventariar_filas_sin_pe(filas)
	combos = combos_a_facturar(pendientes)

	result: dict[str, Any] = {
		"csv_path": csv_path,
		"dry_run": dry_run,
		"modo": "retry_sin_pe",
		"sept_antes": sept_antes,
		"sept_si_count": sept_antes["sept_si_count"],
		"sept_pe_count": sept_antes["sept_pe_count"],
		"filas": len(pendientes),
		"filas_sin_pe": len(pendientes),
		"combos_facturar": len(combos),
		"total_agosto": flt(sum(flt(f["monto_csv"]) for f in pendientes), 2),
		"total_sin_pe": flt(sum(flt(f["monto_csv"]) for f in pendientes), 2),
	}
	print(f"==> Retry sin PE: filas={len(pendientes)} combos={len(combos)}")

	registros: list[dict[str, Any]] = []
	try:
		print("==> Facturas faltantes")
		result["facturacion"] = emitir_facturas_historicas(
			combos, dry_run=dry_run, commit_every=commit_every
		)
		print("==> Cobros pendientes")
		registros = procesar_cobranzas(
			pendientes, dry_run=dry_run, commit_every=commit_every
		)
		result["registros"] = len(registros)
		result["estados"] = dict(Counter(r["estado"] for r in registros))
		sept_despues = assert_septiembre_intacto(sept_antes)
		result["sept_despues"] = sept_despues
		result["septiembre_ok"] = True
		if not dry_run and not in_test:
			frappe.db.commit()
	except Exception:
		if not dry_run and not in_test and not commit_every:
			frappe.db.rollback()
		result["septiembre_ok"] = False
		raise

	destino = Path(out_path or f"{csv_path}.retry_sin_pe.json")
	destino.write_text(
		json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
	)
	result["out_path"] = str(destino)
	if registros:
		aud = Path(f"{csv_path}.retry_sin_pe.auditoria.json")
		aud.write_text(
			json.dumps(registros, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
		)
		result["auditoria_path"] = str(aud)
	_imprimir_control(result)
	return result


def run_prod_dry() -> dict[str, Any]:
	return run(csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv", dry_run=True)


def run_local_apply() -> dict[str, Any]:
	"""Apply en dev.localhost (confirm local-dev)."""
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=False,
		confirm=CONFIRM_LOCAL,
		commit_every=25,
		out_path="/tmp/purga_migracion_apply.json",
	)


def run_local_retry_sin_pe(*, dry_run: bool = False) -> dict[str, Any]:
	"""Reintenta las ~623 filas sin PE en local (CTO histórico + cobro/mora mismo día)."""
	return retry_sin_pe(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=dry_run,
		confirm=CONFIRM_LOCAL,
		commit_every=25,
		out_path="/tmp/purga_retry_sin_pe.json",
	)


# Filas CSV que matchearon «C FED … FLEX» por fuzzy en lugar del arancel FLEX.
_FLEX_RECREATE_FILAS = (2455, 2456, 2459, 2479, 2480)


def recrear_flex_mal_mapeados(
	*,
	csv_path: str = "/tmp/cobranzas_bulk_erp_agosto_2026.csv",
	dry_run: bool = True,
	confirm: str = "",
	filas: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
	"""Emite SI arancel FLEX correcta e imputa cobro (no toca SI federativa).

	Causa: `buscar_linea` matcheaba «U13 FLEX» dentro de «C FED U13 FLEX».
	"""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	target = set(filas or _FLEX_RECREATE_FILAS)
	todas = _filas_csv(csv_path)
	pendientes = [f for f in todas if f["fila"] in target]
	if len(pendientes) != len(target):
		found = {f["fila"] for f in pendientes}
		missing = sorted(target - found)
		frappe.throw(
			_("Filas FLEX no encontradas en CSV: {0}").format(missing),
			frappe.ValidationError,
		)

	sept_antes = snapshot_septiembre()
	combos = combos_a_facturar(pendientes)
	print(f"==> Recrear FLEX filas={sorted(target)} combos={len(combos)} dry_run={dry_run}")
	fact = emitir_facturas_historicas(combos, dry_run=dry_run, commit_every=1)
	regs = procesar_cobranzas(pendientes, dry_run=dry_run, commit_every=1)
	sept_despues = assert_septiembre_intacto(sept_antes)
	if not dry_run and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()
	result = {
		"dry_run": dry_run,
		"filas": sorted(target),
		"facturacion": {
			"creadas_count": fact["creadas_count"],
			"omitidas_count": fact["omitidas_count"],
			"errores_count": fact["errores_count"],
			"errores": fact["errores"],
		},
		"estados": dict(Counter(r["estado"] for r in regs)),
		"registros": regs,
		"sept_antes": sept_antes,
		"sept_despues": sept_despues,
		"septiembre_ok": True,
	}
	Path("/tmp/purga_recrear_flex.json").write_text(
		json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
	)
	print(json.dumps({k: v for k, v in result.items() if k != "registros"}, indent=2, default=str))
	return result


def run_local_recrear_flex(*, dry_run: bool = False) -> dict[str, Any]:
	return recrear_flex_mal_mapeados(dry_run=dry_run, confirm=CONFIRM_LOCAL)


def _origen_desde_remarks_mora(remarks: str | None) -> str:
	raw = (remarks or "").strip()
	if not raw.startswith("Mora al cobro"):
		return ""
	return raw.replace("Mora al cobro", "", 1).strip()


def _mora_tiene_pe_submitted(invoice_name: str) -> bool:
	pe_links = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": invoice_name,
			"parenttype": "Payment Entry",
		},
		fields=["parent"],
	)
	for link in pe_links:
		if frappe.db.get_value("Payment Entry", link.parent, "docstatus") == 1:
			return True
	return False


def _origen_mora_cerrado(origen: str) -> bool:
	"""True si el origen no existe, está cancelado o ya saldado."""
	if not origen or not frappe.db.exists(SALES_INVOICE_DOCTYPE, origen):
		return True
	st = frappe.db.get_value(
		SALES_INVOICE_DOCTYPE, origen, ["docstatus", "outstanding_amount"], as_dict=True
	)
	if not st:
		return True
	return int(st.docstatus) == 2 or flt(st.outstanding_amount) <= 0.005


def inventariar_mora_huerfanas(
	*,
	socio_name: str | None = None,
	socios: set[str] | frozenset[str] | None = None,
) -> list[dict[str, Any]]:
	"""SI mora con outstanding cuyo origen está cerrado.

	Incluye:
	- mora sin PE → candidata a cancelar
	- mora con PE parcial → candidata a Credit Note por el residual
	"""
	from club_management.members.services.mora_al_cobro import periodo_es_ajuste_mora

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	if not campo_socio or not campo_periodo:
		return []

	filters: dict[str, Any] = {"docstatus": 1, "outstanding_amount": [">", 0]}
	if socio_name:
		filters[campo_socio] = socio_name

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=filters,
		fields=["name", campo_socio, campo_periodo, "outstanding_amount", "remarks", "posting_date"],
		order_by="posting_date asc, name asc",
	)
	huerfanas: list[dict[str, Any]] = []
	for row in rows:
		socio = (row.get(campo_socio) or "").strip()
		if socios is not None and socio not in socios:
			continue
		periodo = (row.get(campo_periodo) or "").strip()
		remarks = row.remarks or ""
		es_mora = periodo_es_ajuste_mora(periodo) or remarks.startswith("Mora al cobro")
		if not es_mora:
			continue
		origen = _origen_desde_remarks_mora(remarks)
		if not _origen_mora_cerrado(origen):
			continue
		tiene_pe = _mora_tiene_pe_submitted(row.name)
		huerfanas.append(
			{
				"name": row.name,
				"socio": socio,
				"periodo": periodo,
				"outstanding": flt(row.outstanding_amount),
				"posting_date": str(row.posting_date),
				"origen": origen,
				"remarks": remarks,
				"tiene_pe": tiene_pe,
				"accion": "credit_note" if tiene_pe else "cancel",
			}
		)
	return huerfanas


def _credit_note_mora_residual(invoice_name: str, monto: float) -> str:
	"""CN por outstanding residual de una SI de mora (idempotente por remarks)."""
	from frappe.utils import add_to_date, get_datetime, now_datetime

	monto = flt(monto, 2)
	if monto <= 0.005:
		return ""

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	socio_name = invoice.get(campo_socio) if campo_socio else None
	remarks_cn = f"CN mora huérfana {invoice_name}"
	if campo_socio and socio_name:
		existente = frappe.db.exists(
			SALES_INVOICE_DOCTYPE,
			{
				campo_socio: socio_name,
				"docstatus": 1,
				"is_return": 1,
				"return_against": invoice_name,
				"remarks": remarks_cn,
			},
		)
		if existente:
			return str(existente)

	origen_row = (invoice.get("items") or [None])[0]
	if not origen_row:
		frappe.throw(_("Mora {0} sin líneas para CN.").format(invoice_name))

	company = invoice.company or _default_company()
	item_line: dict[str, Any] = {
		"item_code": origen_row.item_code,
		"qty": -1.0,
		"rate": monto,
		"description": _("Regularización mora huérfana {0}").format(invoice_name),
		"sales_invoice_item": origen_row.name,
	}
	preferred_cc = origen_row.get("cost_center") or resolve_cost_center_item(
		origen_row.item_code, company
	)
	if preferred_cc:
		item_line["cost_center"] = preferred_cc

	posting_cn = getdate(invoice.posting_date)
	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": invoice.customer,
		"company": company,
		"is_return": 1,
		"return_against": invoice_name,
		"update_outstanding_for_self": 0,
		"posting_date": posting_cn,
		"due_date": posting_cn,
		"set_posting_time": 1,
		"disable_rounded_total": 1,
		"remarks": remarks_cn,
		"items": [item_line],
	}
	origen_ts = get_datetime(invoice.get("posting_date"))
	if invoice.meta.has_field("posting_time") and invoice.get("posting_time"):
		try:
			origen_ts = get_datetime(f"{invoice.posting_date} {invoice.posting_time}")
		except Exception:
			origen_ts = get_datetime(invoice.posting_date)
	cn_ts = add_to_date(origen_ts, seconds=5)
	payload["posting_time"] = cn_ts.strftime("%H:%M:%S") if getdate(cn_ts) == posting_cn else "00:00:01"
	if campo_socio and socio_name:
		payload[campo_socio] = socio_name
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo and invoice.get(campo_periodo):
		payload[campo_periodo] = invoice.get(campo_periodo)

	cn = frappe.get_doc(payload)
	cn.flags.ignore_permissions = True
	cn.insert(ignore_permissions=True)
	cn.submit()
	return cn.name


def cancelar_mora_huerfanas(
	*,
	socio_name: str | None = None,
	socios: set[str] | frozenset[str] | None = None,
	dry_run: bool = True,
	confirm: str = "",
	commit_every: int = 25,
) -> dict[str, Any]:
	"""Limpia mora huérfana: cancel si sin PE; CN residual si hay PE parcial."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	candidatas = inventariar_mora_huerfanas(socio_name=socio_name, socios=socios)
	in_test = bool(getattr(frappe.flags, "in_test", False))
	hechos: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []

	print(f"==> Mora huérfanas candidatas={len(candidatas)} dry_run={dry_run}")
	for row in candidatas:
		accion = row.get("accion") or "cancel"
		if dry_run:
			hechos.append({**row, "dry_run": True})
			continue
		try:
			if accion == "credit_note":
				cn = _credit_note_mora_residual(row["name"], flt(row["outstanding"]))
				hechos.append({**row, "credit_note": cn})
			else:
				doc = frappe.get_doc(SALES_INVOICE_DOCTYPE, row["name"])
				doc.flags.ignore_permissions = True
				doc.cancel()
				hechos.append({**row, "cancelada": True})
			if commit_every and not in_test and len(hechos) % commit_every == 0:
				frappe.db.commit()
				print(f"  mora limpiadas={len(hechos)}/{len(candidatas)}")
		except Exception as exc:  # noqa: BLE001
			if not in_test:
				frappe.db.rollback()
			errores.append({"name": row["name"], "accion": accion, "error": str(exc)[:280]})

	if not dry_run and commit_every and not in_test:
		frappe.db.commit()

	total = flt(sum(flt(r.get("outstanding")) for r in hechos), 2)
	result = {
		"dry_run": dry_run,
		"socio": socio_name or "",
		"candidatas_count": len(candidatas),
		"canceladas_count": len(hechos),
		"errores_count": len(errores),
		"total_outstanding": total,
		"canceladas": hechos if dry_run or len(hechos) <= 200 else hechos[:200],
		"errores": errores[:50],
	}
	Path("/tmp/purga_mora_huerfanas.json").write_text(
		json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
	)
	print(
		f"  mora fin: candidatas={len(candidatas)} "
		f"limpiadas={len(hechos)} errores={len(errores)} total=${total:,.2f}"
	)
	return result


def cancelar_mora_huerfana_socio(
	socio_name: str,
	*,
	dry_run: bool = True,
	confirm: str = "",
) -> dict[str, Any]:
	"""Atajo: limpia mora huérfana de un socio."""
	return cancelar_mora_huerfanas(socio_name=socio_name, dry_run=dry_run, confirm=confirm)


def run_local_cancelar_mora_8832(*, dry_run: bool = False) -> dict[str, Any]:
	return cancelar_mora_huerfanas(socio_name="8832", dry_run=dry_run, confirm=CONFIRM_LOCAL)


def run_local_cancelar_mora_huerfanas(*, dry_run: bool = False) -> dict[str, Any]:
	"""Limpieza site-wide de mora huérfana en local."""
	return cancelar_mora_huerfanas(dry_run=dry_run, confirm=CONFIRM_LOCAL, commit_every=25)


def run_prod_apply() -> dict[str, Any]:
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=False,
		confirm=CONFIRM_PURGE_PROD,
		commit_every=25,
		out_path="/tmp/purga_migracion_apply.json",
	)


def run_prod_retry_sin_pe(*, dry_run: bool = False) -> dict[str, Any]:
	"""Reintenta filas ≤08/2026 sin PE en producción."""
	return retry_sin_pe(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=dry_run,
		confirm=CONFIRM_PURGE_PROD,
		commit_every=25,
		out_path="/tmp/purga_retry_sin_pe.json",
	)


def run_prod_recrear_flex(*, dry_run: bool = False) -> dict[str, Any]:
	"""Recrea SI/PE FLEX mal mapeados en producción."""
	return recrear_flex_mal_mapeados(dry_run=dry_run, confirm=CONFIRM_PURGE_PROD)


def run_prod_cancelar_mora_huerfanas(*, dry_run: bool = False) -> dict[str, Any]:
	"""Limpieza site-wide de mora huérfana en producción."""
	return cancelar_mora_huerfanas(
		dry_run=dry_run, confirm=CONFIRM_PURGE_PROD, commit_every=25
	)
