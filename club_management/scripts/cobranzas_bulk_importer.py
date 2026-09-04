"""Importer consolidado de cobranzas con invariante de no-pérdida.

Spec: `club_management/specs/carga_masiva_cobranzas.md`
(sección «Importer consolidado con invariante de no-pérdida»)

Procesa el CSV consolidado del mes (una fila = un concepto cobrado) resolviendo
facturación e imputación fila por fila. Toda fila termina en un estado terminal
explícito y queda registrada en el log de auditoría: `len(log) == len(csv)` y
`Σ monto_csv(log) == Σ monto_csv(csv)`.

    # Dry-run
    bench --site dev.localhost execute \\
        club_management.scripts.cobranzas_bulk_importer.run \\
        --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv"}'

    # Apply producción
    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.cobranzas_bulk_importer.apply_prod_agosto
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

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
from club_management.members.services.cobranza_periodica import resolve_fechas_factura_mensual
from club_management.members.services.mora_al_cobro import (
	calcular_exigido_linea_factura,
	resolver_tramo_mora,
)
from club_management.scripts.bulk_io import (
	cell,
	ensure_bulk_apply_allowed,
	find_socio,
	parse_fecha,
	parse_monto,
	read_bulk_rows,
)
from club_management.scripts.bulk_payments import (
	_pe_existente,
	_registrar_cobro_concepto_informe,
	map_medio_pago,
)
from club_management.scripts.informe_concepto_cobranza import (
	ITEM_CUOTA_COMPLEMENTARIA,
	TARIFAS_PATIN_AGOSTO_2026,
	buscar_cargo_socio_cuota_complementaria,
	buscar_linea_factura_concepto,
	es_concepto_carnet,
	es_cuota_complementaria,
	periodo_es_adelantado,
	linea_cuota_complementaria_en_periodo,
	monto_imputado_concepto_informe_en_rango,
	normalizar_concepto_informe,
	parse_referencia_informe,
	referencia_informe,
	resolver_item_codes_concepto,
)

AUDITORIA_COLUMNAS: tuple[str, ...] = (
	"fila",
	"nro_socio",
	"socio",
	"fecha_pago",
	"periodo",
	"concepto",
	"monto_csv",
	"estado",
	"item_code",
	"sales_invoice",
	"sales_invoice_emitida",
	"payment_entry",
	"monto_imputado",
	"mora_pct_esperado",
	"mora_monto",
	"sales_invoice_mora",
	"saldo_favor",
	"mensaje",
)

ESTADOS_OK: tuple[str, ...] = (
	"imputado",
	"imputado_con_facturacion",
	"imputado_con_saldo_favor",
	"ya_imputado",
	"ya_saldada",
)

ESTADOS_EXCLUIDOS: tuple[str, ...] = ("excluido_carnet", "excluido_adelantado")

ESTADOS_ERROR: tuple[str, ...] = (
	"error_socio_no_encontrado",
	"error_fecha_invalida",
	"error_medio_pago_invalido",
	"error_monto_invalido",
	"error_concepto_sin_mapeo",
	"error_facturacion",
	"error_cobro",
)


def _mora_pct_esperado(periodo: str, fecha: Any) -> float:
	"""Recargo esperado según tramo (mes del período vs fecha de cobro)."""
	settings = get_club_settings()
	pct_post = flt(
		settings.recargo_post_vencimiento_pct
		if settings.recargo_post_vencimiento_pct is not None
		else 10
	)
	pct_extra = flt(
		settings.recargo_mes_vencido_pct if settings.recargo_mes_vencido_pct is not None else 5
	)
	tramo = resolver_tramo_mora(
		periodo,
		fecha,
		dia_primer_vencimiento=int(settings.dia_primer_vencimiento or 10),
		dia_segundo_vencimiento=settings.dia_segundo_vencimiento or "20",
	)
	if tramo == "post_primer":
		return pct_post
	if tramo == "post_segundo":
		return flt(pct_post + pct_extra, 2)
	return 0.0


def _buscar_pe_reconciliable(
	socio_name: str,
	fecha: Any,
	monto: float,
	periodo: str,
	concepto: str,
	claimed: set[str],
) -> tuple[str, bool] | None:
	"""PE existente del socio (misma fecha y monto) atribuible a esta fila.

	Devuelve `(pe_name, referencia_correcta)`; `referencia_correcta=False`
	significa que el `reference_no` INF tiene otro concepto/fila y debe corregirse.
	"""
	campo = _campo_socio_en("Customer")
	customer = frappe.db.get_value("Customer", {campo: socio_name}, "name") if campo else None
	if not customer:
		return None
	norm = normalizar_concepto_informe(concepto)
	pes = frappe.get_all(
		"Payment Entry",
		filters={
			"party": customer,
			"docstatus": 1,
			"posting_date": getdate(fecha),
			"paid_amount": ["between", [flt(monto) - 0.01, flt(monto) + 0.01]],
		},
		fields=["name", "reference_no"],
		order_by="name asc",
	)
	exacto: tuple[str, bool] | None = None
	corregible: tuple[str, bool] | None = None
	for pe in pes:
		if pe.name in claimed:
			continue
		parsed = parse_referencia_informe(pe.reference_no)
		if not parsed:
			continue
		if parsed["periodo"] != (periodo or "").strip():
			continue
		if abs(flt(parsed["monto"]) - flt(monto)) > 0.01:
			continue
		if normalizar_concepto_informe(str(parsed["concepto"])) == norm:
			exacto = exacto or (pe.name, True)
		else:
			corregible = corregible or (pe.name, False)
	return exacto or corregible


def _monto_base_sin_mora(monto_csv: float, mora_pct: float) -> float:
	"""Descuenta el recargo del CSV para facturar solo la base.

	Si el CSV ya trae la base (p. ej. $28.500 pagados en día con mora 10 %),
	dividir produciría basura ($25.909,09): en ese caso se conserva el monto.
	"""
	pct = flt(mora_pct)
	monto = flt(monto_csv, 2)
	if pct <= 0:
		return monto
	base = flt(monto) / (1.0 + pct / 100.0)
	base_redondeada = flt(round(base), 2)
	# CSV con mora incluida → base casi entera (28500, 21000, …)
	if abs(base - base_redondeada) <= 0.05:
		return base_redondeada
	# CSV ya era base entera; no descontar
	return monto


def _rate_factura_concepto(
	item_code: str,
	periodo: str,
	*,
	monto_csv: float,
	mora_pct: float,
) -> float:
	"""Rate de SI: tarifas patín agosto congeladas, o base sin mora del CSV."""
	if (periodo or "").strip() == "08/2026" and item_code in TARIFAS_PATIN_AGOSTO_2026:
		return flt(TARIFAS_PATIN_AGOSTO_2026[item_code], 2)
	return _monto_base_sin_mora(monto_csv, mora_pct)


def _emitir_factura_concepto(
	socio_name: str,
	periodo: str,
	concepto: str,
	item_code: str,
	*,
	monto: float,
	mora_pct: float,
) -> str:
	"""Emite SI de una línea: rate base sin mora (mora se aplica al cobro)."""
	from club_management.members.services.cobranza_manual import _submit_sales_invoice_concepto

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Sales Invoice sin campo de socio configurado."), frappe.ValidationError)
	customer = ensure_customer_for_socio(socio_name, skip_permission_check=True)
	ref = reference_date_desde_periodo(periodo)
	posting, due = resolve_fechas_factura_mensual(
		ref,
		int(get_club_settings().dia_primer_vencimiento or 10),
	)
	rate = _rate_factura_concepto(item_code, periodo, monto_csv=monto, mora_pct=mora_pct)
	descripcion = f"{concepto} ({periodo})"
	linea: dict[str, Any] = {
		"item_code": item_code,
		"qty": 1,
		"rate": rate,
		"description": descripcion,
	}
	company = _default_company()
	cost_center = resolve_cost_center_item(item_code, company)
	if cost_center:
		linea["cost_center"] = cost_center
	return _submit_sales_invoice_concepto(
		socio_name=socio_name,
		customer=customer,
		campo_socio=campo_socio,
		periodo=periodo,
		posting=posting,
		due=due,
		item=linea,
	)


def _facturar_cto_comp(socio_name: str, periodo: str, concepto: str, monto: float) -> str | None:
	"""Asegura SI de cuota complementaria: crea el cargo si falta y prepaga el período."""
	from club_management.members.services.cargo_extra_prepago import prepagar_cargo_socio
	from club_management.members.services.cargo_socio import crear_cargo_extra_socio

	cargo = buscar_cargo_socio_cuota_complementaria(socio_name, concepto)
	if not cargo:
		anio = (periodo or "").split("/")[-1] or str(getdate(today()).year)
		result = crear_cargo_extra_socio(
			socio=socio_name,
			titulo=(concepto or "").strip()[:120],
			tipo_cargo="Otro",
			modo_cobro="Recurrente",
			item=ITEM_CUOTA_COMPLEMENTARIA,
			monto=flt(monto),
			fecha_desde=str(reference_date_desde_periodo(periodo)),
			fecha_hasta=f"{anio}-12-31",
			observaciones="Alta desde importer consolidado de cobranzas",
			facturar_mes_corriente=False,
		)
		cargo = {"name": result.get("cargo")}
	if not cargo or not cargo.get("name"):
		return None
	prepago = prepagar_cargo_socio(
		cargo["name"],
		periodos=[periodo],
		reference_date=reference_date_desde_periodo(periodo),
	)
	created = list(prepago.get("sales_invoices") or [])
	if created:
		return created[0]
	match = linea_cuota_complementaria_en_periodo(
		socio_name, periodo, concepto, solo_impagas=True, reservadas=set()
	)
	return match[0] if match else None


def _procesar_fila(
	idx: int,
	raw: dict[str, str],
	*,
	dry_run: bool,
	reconcile: bool,
	auto_facturar: bool,
	tolerance: float,
	fecha_desde: str,
	fecha_hasta: str,
	claimed_pes: set[str],
	consumido: dict[tuple[str, str, str], float],
) -> dict[str, Any]:
	nro = cell(raw, "nro_socio", "numero_socio", "nro")
	dni = cell(raw, "dni")
	monto = parse_monto(cell(raw, "monto_abonado", "monto"))
	fecha_raw = cell(raw, "fecha_pago", "fecha")
	medio_raw = cell(raw, "medio_pago", "medio")
	periodo = cell(raw, "periodo", "periodo_cobro")
	concepto = cell(raw, "concepto")
	referencia_csv = cell(raw, "referencia_comprobante", "referencia", "comprobante")

	registro: dict[str, Any] = {
		"fila": idx,
		"nro_socio": nro,
		"socio": "",
		"fecha_pago": fecha_raw,
		"periodo": periodo,
		"concepto": concepto,
		"monto_csv": flt(monto, 2),
		"estado": "",
		"item_code": "",
		"sales_invoice": "",
		"sales_invoice_emitida": "",
		"payment_entry": "",
		"monto_imputado": 0.0,
		"mora_pct_esperado": 0.0,
		"mora_monto": 0.0,
		"sales_invoice_mora": "",
		"saldo_favor": 0.0,
		"mensaje": "",
	}

	def terminar(estado: str, mensaje: str = "") -> dict[str, Any]:
		registro["estado"] = estado
		if mensaje:
			registro["mensaje"] = (registro["mensaje"] + "; " + mensaje).strip("; ")
		return registro

	socio_name = find_socio(nro_socio=nro, dni=dni)
	registro["socio"] = socio_name or ""
	if es_concepto_carnet(concepto):
		return terminar("excluido_carnet", "CARNET fuera de imputación masiva")
	if not socio_name:
		return terminar("error_socio_no_encontrado")

	fecha = parse_fecha(fecha_raw)
	if not fecha:
		return terminar("error_fecha_invalida")
	if fecha > getdate(today()):
		return terminar("error_fecha_invalida", "fecha futura")
	registro["fecha_pago"] = fecha.isoformat()

	medio = map_medio_pago(medio_raw)
	if not medio:
		return terminar("error_medio_pago_invalido", medio_raw)

	if monto <= 0:
		return terminar("error_monto_invalido")

	if not periodo:
		return terminar("error_fecha_invalida", "fila sin periodo")

	cierre_pago = fecha.strftime("%m/%Y")
	if periodo_es_adelantado(periodo, cierre_pago):
		return terminar(
			"excluido_adelantado",
			"período posterior al mes de cobro; revisión manual Secretaría",
		)

	registro["mora_pct_esperado"] = _mora_pct_esperado(periodo, fecha)

	ref_canonica = referencia_informe(
		fila=idx, numero_socio=nro or socio_name, periodo=periodo, monto=monto, concepto=concepto
	)

	# --- Idempotencia -------------------------------------------------
	pe_previo = _pe_existente(socio_name, ref_canonica)
	if not pe_previo and referencia_csv:
		pe_previo = _pe_existente(socio_name, referencia_csv)
	if pe_previo:
		claimed_pes.add(pe_previo)
		registro["payment_entry"] = pe_previo
		registro["monto_imputado"] = flt(monto, 2)
		return terminar("ya_imputado", "referencia ya procesada")

	# --- Reconciliación contra PEs existentes -------------------------
	clave_consumo = (socio_name, normalizar_concepto_informe(concepto), (periodo or "").strip())
	if reconcile:
		match_pe = _buscar_pe_reconciliable(
			socio_name, fecha, monto, periodo, concepto, claimed_pes
		)
		if match_pe:
			pe_name, ref_ok = match_pe
			claimed_pes.add(pe_name)
			registro["payment_entry"] = pe_name
			registro["monto_imputado"] = flt(monto, 2)
			consumido[clave_consumo] = consumido.get(clave_consumo, 0.0) + flt(monto, 2)
			if ref_ok:
				return terminar("ya_imputado", "PE existente con referencia equivalente")
			if not dry_run:
				frappe.db.set_value(
					"Payment Entry", pe_name, "reference_no", ref_canonica, update_modified=False
				)
			return terminar("ya_imputado", "referencia_corregida")

		imputado_previo = monto_imputado_concepto_informe_en_rango(
			socio_name,
			concepto,
			periodo,
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
		)
		disponible = flt(imputado_previo - consumido.get(clave_consumo, 0.0), 2)
		if disponible >= flt(monto, 2) - tolerance:
			consumido[clave_consumo] = consumido.get(clave_consumo, 0.0) + flt(monto, 2)
			registro["monto_imputado"] = flt(monto, 2)
			return terminar("ya_imputado", "concepto ya imputado en el rango")

	# --- Resolución de línea de factura -------------------------------
	item_codes = resolver_item_codes_concepto(concepto, socio_name=socio_name, monto_abonado=monto)
	es_cto = es_cuota_complementaria(concepto)
	if not item_codes and not es_cto:
		return terminar("error_concepto_sin_mapeo")

	match = buscar_linea_factura_concepto(
		socio_name,
		periodo,
		concepto,
		monto_abonado=monto,
		reservadas=set(),
		solo_impagas=True,
	)
	invoice_name: str | None = None
	facturada_ahora = False
	if match:
		invoice_name, item_code, _line_base = match
		registro["sales_invoice"] = invoice_name
		registro["item_code"] = item_code
	else:
		match_saldada = buscar_linea_factura_concepto(
			socio_name,
			periodo,
			concepto,
			monto_abonado=monto,
			reservadas=set(),
			solo_impagas=False,
		)
		if match_saldada:
			outstanding = flt(
				frappe.db.get_value(
					SALES_INVOICE_DOCTYPE, match_saldada[0], "outstanding_amount"
				)
				or 0,
				2,
			)
			if outstanding <= 0.005:
				registro["sales_invoice"] = match_saldada[0]
				registro["item_code"] = match_saldada[1]
				registro["monto_imputado"] = flt(monto, 2)
				return terminar(
					"ya_saldada", "línea saldada sin PE atribuible a esta fila en el rango"
				)
			invoice_name = match_saldada[0]
			registro["sales_invoice"] = invoice_name
			registro["item_code"] = match_saldada[1]
		elif auto_facturar:
			if dry_run:
				registro["item_code"] = item_codes[0] if item_codes else ITEM_CUOTA_COMPLEMENTARIA
				return terminar(
					"imputado_con_facturacion", "dry-run: facturaría SI de una línea y cobraría"
				)
			try:
				if es_cto:
					invoice_name = _facturar_cto_comp(socio_name, periodo, concepto, monto)
				else:
					invoice_name = _emitir_factura_concepto(
						socio_name,
						periodo,
						concepto,
						item_codes[0],
						monto=monto,
						mora_pct=flt(registro["mora_pct_esperado"]),
					)
			except Exception as exc:  # noqa: BLE001 — el estado terminal registra el error
				if not getattr(frappe.flags, "in_test", False):
					frappe.db.rollback()
				return terminar("error_facturacion", str(exc)[:280])
			if not invoice_name:
				return terminar("error_facturacion", "no se pudo emitir la SI del concepto")
			facturada_ahora = True
			registro["sales_invoice"] = invoice_name
			registro["sales_invoice_emitida"] = invoice_name
			registro["item_code"] = item_codes[0] if item_codes else ITEM_CUOTA_COMPLEMENTARIA
		else:
			return terminar("error_facturacion", "concepto sin factura y auto_facturar=False")

	# --- Mora esperada sobre valor facturado (informativa) ------------
	if invoice_name and registro["item_code"]:
		try:
			info = calcular_exigido_linea_factura(
				invoice_name,
				registro["item_code"],
				socio_name,
				posting_date=fecha,
				base="facturado",
			)
			exigido = flt(info.get("monto_exigido"), 2)
			registro["mora_monto"] = flt(
				max(0.0, exigido - flt(info.get("line_base") or 0)), 2
			)
			if exigido > 0 and abs(exigido - flt(monto, 2)) > tolerance:
				registro["mensaje"] = (
					registro["mensaje"]
					+ f"; diferencia_mora: exigido {exigido} vs abonado {flt(monto, 2)}"
				).strip("; ")
		except Exception:  # noqa: BLE001 — dato informativo, no bloquea la imputación
			pass

	# --- Imputación ----------------------------------------------------
	if dry_run:
		consumido[clave_consumo] = consumido.get(clave_consumo, 0.0) + flt(monto, 2)
		registro["monto_imputado"] = flt(monto, 2)
		return terminar(
			"imputado_con_facturacion" if facturada_ahora else "imputado",
			"dry-run: no persiste",
		)

	try:
		result = _registrar_cobro_concepto_informe(
			socio_name,
			invoice_name,
			monto,
			mode_of_payment=medio,
			posting_date=fecha,
			reference_no=ref_canonica,
			auto_submit=True,
			concepto=concepto,
			periodo_fila=periodo,
		)
	except frappe.ValidationError as exc:
		if not getattr(frappe.flags, "in_test", False):
			frappe.db.rollback()
		return terminar("error_cobro", str(exc)[:280])
	except Exception as exc:  # noqa: BLE001
		if not getattr(frappe.flags, "in_test", False):
			frappe.db.rollback()
		return terminar("error_cobro", str(exc)[:280])

	pes = result.get("payment_entries") or []
	claimed_pes.update(pes)
	registro["payment_entry"] = ";".join(pes)
	saldo_favor = flt(result.get("saldo_favor") or 0, 2)
	registro["saldo_favor"] = saldo_favor
	registro["monto_imputado"] = flt(monto - saldo_favor, 2)
	consumido[clave_consumo] = consumido.get(clave_consumo, 0.0) + flt(monto, 2)

	mora_sis = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"docstatus": 1, "remarks": ["like", f"%Mora al cobro {invoice_name}%"]},
		pluck="name",
	)
	registro["sales_invoice_mora"] = ";".join(mora_sis)

	if facturada_ahora:
		return terminar("imputado_con_facturacion")
	if saldo_favor > 0.005:
		return terminar("imputado_con_saldo_favor")
	return terminar("imputado")


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	reconcile: bool = True,
	auto_facturar: bool = True,
	fecha_desde: str | None = None,
	fecha_hasta: str | None = None,
	tolerance: float = 0.5,
	limit: int | None = None,
	auditoria_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	"""Procesa el CSV consolidado. Toda fila queda en el log de auditoría."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	ensure_bulk_apply_allowed(dry_run=dry_run, confirm=confirm)
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	frappe.flags.mute_emails = True
	in_test = bool(getattr(frappe.flags, "in_test", False))

	rows = read_bulk_rows(csv_path)
	if limit is not None:
		rows = rows[:limit]

	fechas = [parse_fecha(cell(r, "fecha_pago", "fecha")) for r in rows]
	fechas_validas = [f for f in fechas if f]
	rango_desde = fecha_desde or (min(fechas_validas).isoformat() if fechas_validas else today())
	rango_hasta = fecha_hasta or (max(fechas_validas).isoformat() if fechas_validas else today())

	claimed_pes: set[str] = set()
	consumido: dict[tuple[str, str, str], float] = {}
	registros: list[dict[str, Any]] = []
	aplicadas = 0

	for idx, raw in enumerate(rows, start=2):
		registro = _procesar_fila(
			idx,
			raw,
			dry_run=dry_run,
			reconcile=reconcile,
			auto_facturar=auto_facturar,
			tolerance=tolerance,
			fecha_desde=rango_desde,
			fecha_hasta=rango_hasta,
			claimed_pes=claimed_pes,
			consumido=consumido,
		)
		registros.append(registro)
		if not dry_run and registro["estado"].startswith("imputado"):
			aplicadas += 1
			if commit_every and aplicadas % commit_every == 0 and not in_test:
				frappe.db.commit()
				print(f"  aplicadas={aplicadas} fila={idx} estado={registro['estado']}")

	if not dry_run and aplicadas and not in_test:
		frappe.db.commit()

	# Invariante de no-pérdida
	total_csv = flt(sum(flt(r["monto_csv"]) for r in registros), 2)
	assert len(registros) == len(rows), "invariante: len(log) != len(csv)"

	estados = Counter(r["estado"] for r in registros)
	total_imputado = flt(
		sum(flt(r["monto_imputado"]) for r in registros if r["estado"] in ESTADOS_OK and r["estado"] != "ya_saldada"),
		2,
	)
	total_ya_saldado = flt(
		sum(flt(r["monto_csv"]) for r in registros if r["estado"] == "ya_saldada"), 2
	)
	total_saldo_favor = flt(sum(flt(r["saldo_favor"]) for r in registros), 2)
	total_error = flt(
		sum(flt(r["monto_csv"]) for r in registros if r["estado"] in ESTADOS_ERROR), 2
	)
	total_excluido = flt(
		sum(flt(r["monto_csv"]) for r in registros if r["estado"] in ESTADOS_EXCLUIDOS), 2
	)
	carnet_log = [
		{
			"fila": r["fila"],
			"nro_socio": r["nro_socio"],
			"socio": r["socio"],
			"periodo": r["periodo"],
			"concepto": r["concepto"],
			"monto_csv": flt(r["monto_csv"], 2),
			"motivo": r["estado"],
		}
		for r in registros
		if r["estado"] == "excluido_carnet"
	]
	revision_manual = [
		{
			"motivo": r["estado"],
			"fila": r["fila"],
			"nro_socio": r["nro_socio"],
			"socio": r["socio"],
			"periodo": r["periodo"],
			"concepto": r["concepto"],
			"monto_csv": flt(r["monto_csv"], 2),
		}
		for r in registros
		if r["estado"]
		in ("excluido_carnet", "excluido_adelantado", "error_socio_no_encontrado")
	]

	destino = Path(auditoria_path or f"{csv_path}.auditoria.csv")
	destino.parent.mkdir(parents=True, exist_ok=True)
	with destino.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=list(AUDITORIA_COLUMNAS))
		writer.writeheader()
		writer.writerows(registros)

	resumen = {
		"csv_path": csv_path,
		"dry_run": dry_run,
		"reconcile": reconcile,
		"fecha_desde": rango_desde,
		"fecha_hasta": rango_hasta,
		"filas": len(registros),
		"total_csv": total_csv,
		"estados": dict(estados),
		"total_imputado": total_imputado,
		"total_ya_saldado": total_ya_saldado,
		"total_saldo_favor": total_saldo_favor,
		"total_error": total_error,
		"total_excluido": total_excluido,
		"carnet": {
			"filas": len(carnet_log),
			"monto": flt(sum(flt(r["monto_csv"]) for r in carnet_log), 2),
			"detalle": carnet_log,
		},
		"revision_manual": revision_manual,
		"auditoria_path": str(destino),
	}
	rev_path = Path(f"{csv_path}.revision_manual.csv")
	with rev_path.open("w", encoding="utf-8", newline="") as handle:
		fields = ["motivo", "fila", "nro_socio", "socio", "periodo", "concepto", "monto_csv"]
		writer = csv.DictWriter(handle, fieldnames=fields)
		writer.writeheader()
		writer.writerows(revision_manual)
	resumen["revision_manual_path"] = str(rev_path)
	resumen_path = Path(f"{csv_path}.resumen.json")
	resumen_path.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
	resumen["resumen_path"] = str(resumen_path)

	print("\n" + "=" * 72)
	print(f" IMPORTER CONSOLIDADO — {'SIMULACIÓN' if dry_run else 'EJECUTADO'}")
	print("=" * 72)
	print(f" filas: {resumen['filas']}  total_csv: {total_csv:,.2f}")
	for estado, cant in sorted(estados.items()):
		print(f"   {estado:32s}: {cant}")
	print(
		f" imputado: {total_imputado:,.2f}  ya_saldado: {total_ya_saldado:,.2f}"
		f"  saldo_favor: {total_saldo_favor:,.2f}  error: {total_error:,.2f}"
		f"  excluido: {total_excluido:,.2f}"
	)
	if revision_manual:
		print(f" revisión Secretaría: {len(revision_manual)} filas → {rev_path}")
		for motivo, cant in Counter(r["motivo"] for r in revision_manual).items():
			print(f"   {motivo}: {cant}")
	print("=" * 72 + "\n")
	return resumen


def dry_run_prod_agosto() -> dict[str, Any]:
	"""Atajo dry-run producción (CSV agosto 2026 en /tmp)."""
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=True,
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
	)


def apply_prod_agosto() -> dict[str, Any]:
	"""Apply post-reset: factura base sin mora + imputa CSV (sin reconciliar PE viejos)."""
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		dry_run=False,
		reconcile=False,
		auto_facturar=True,
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
		confirm="APPLY_PROD",
	)


def apply_retry_errores_agosto() -> dict[str, Any]:
	"""Reaplica solo filas `error_facturacion` / `ya_saldada` del último log de auditoría."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	csv_path = "/tmp/cobranzas_bulk_erp_agosto_2026.csv"
	auditoria = Path(f"{csv_path}.auditoria.csv")
	if not auditoria.is_file():
		frappe.throw(_("No hay auditoría en {0}").format(auditoria), frappe.ValidationError)

	retry_estados = {"error_facturacion", "ya_saldada"}
	filas_retry: set[int] = set()
	with auditoria.open(encoding="utf-8", newline="") as handle:
		for row in csv.DictReader(handle):
			if row.get("estado") in retry_estados:
				filas_retry.add(int(row["fila"]))

	original = list(read_bulk_rows(csv_path))
	# read_bulk_rows es 0-index; CSV data row 0 == auditoría fila 2
	subset = [original[i] for i in range(len(original)) if (i + 2) in filas_retry]
	retry_path = Path("/tmp/cobranzas_bulk_erp_agosto_2026_retry.csv")
	if not subset:
		return {"filas": 0, "mensaje": "nada para reintentar"}

	with open(csv_path, encoding="utf-8", newline="") as handle:
		reader = csv.DictReader(handle)
		fieldnames = reader.fieldnames or list(subset[0].keys())
	with retry_path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
		writer.writeheader()
		writer.writerows(subset)

	print(f"reintento {len(subset)} filas → {retry_path}")
	return run(
		csv_path=str(retry_path),
		dry_run=False,
		reconcile=False,
		auto_facturar=True,
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
		confirm="APPLY_PROD",
	)
