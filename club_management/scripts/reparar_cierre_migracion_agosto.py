"""Reparación de cierre: mora residual, alias padrón y adelantos 09/2026.

Spec: `club_management/specs/reparacion_cierre_migracion_agosto.md`

    bench --site SITE execute \\
        club_management.scripts.reparar_cierre_migracion_agosto.run_prod \\
        --kwargs '{"dry_run": true}'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	erpnext_cobranza_disponible,
)
from club_management.scripts.bulk_io import (
	CONFIRM_LOCAL,
	cell,
	find_socio,
	parse_fecha,
	parse_monto,
	read_bulk_rows,
)
from club_management.scripts.bulk_payments import (
	_registrar_cobro_concepto_informe,
	map_medio_pago,
)
from club_management.scripts.cobranzas_bulk_importer import (
	_emitir_factura_concepto,
	_facturar_cto_comp,
	_pe_existente,
)
from club_management.scripts.informe_concepto_cobranza import (
	buscar_linea_factura_concepto,
	es_concepto_carnet,
	es_cuota_complementaria,
	periodo_es_adelantado,
	referencia_informe,
	resolver_item_codes_concepto,
)
from club_management.scripts.purge_historical_data_pre_september import (
	CONFIRM_PURGE_PROD,
	PERIODO_CIERRE,
	_ensure_purge_allowed,
	_filas_csv,
	cancelar_mora_huerfanas,
	periodo_leq,
)

# Padrón CSV histórico → Socio canónico en ERP
SOCIO_ALIAS_PADRON: dict[str, str] = {
	"12009": "9484",
	"11755": "3838",
}

CSV_PROD = "/tmp/cobranzas_bulk_erp_agosto_2026.csv"


def resolve_socio_csv(nro_socio: str, *, dni: str = "") -> str | None:
	"""Resuelve nro CSV con alias de padrón, luego `find_socio`."""
	nro = (nro_socio or "").strip()
	canonico = SOCIO_ALIAS_PADRON.get(nro, nro)
	return find_socio(nro_socio=canonico, dni=dni) or find_socio(nro_socio=nro, dni=dni)


def socios_imputados_desde_csv(csv_path: str) -> set[str]:
	"""Socios del CSV (con alias) que existen en el sistema."""
	out: set[str] = set()
	for raw in read_bulk_rows(csv_path):
		nro = cell(raw, "nro_socio", "numero_socio", "nro")
		dni = cell(raw, "dni")
		socio = resolve_socio_csv(nro, dni=dni)
		if socio:
			out.add(socio)
	return out


def _filas_con_alias(csv_path: str) -> list[dict[str, Any]]:
	"""Como `_filas_csv` pero aplica alias de padrón."""
	filas = _filas_csv(csv_path)
	for f in filas:
		nro = (f.get("nro_socio") or "").strip()
		if nro in SOCIO_ALIAS_PADRON or not f.get("socio"):
			resolved = resolve_socio_csv(nro, dni=f.get("dni") or "")
			if resolved:
				f["socio"] = resolved
				f["nro_alias"] = SOCIO_ALIAS_PADRON.get(nro, "")
	return filas


def _pe_existe_ref(ref: str) -> bool:
	return bool(frappe.db.exists("Payment Entry", {"reference_no": ref[:140], "docstatus": 1}))


def _procesar_fila_imputacion(
	f: dict[str, Any],
	*,
	dry_run: bool,
	allow_adelantado: bool,
) -> dict[str, Any]:
	"""Factura (si falta) e imputa una fila CSV. Soporta 09/2026 si allow_adelantado."""
	reg: dict[str, Any] = {
		"fila": f["fila"],
		"nro_socio": f["nro_socio"],
		"socio": f.get("socio") or "",
		"periodo": f["periodo"],
		"concepto": f["concepto"],
		"monto_csv": flt(f["monto_csv"], 2),
		"fecha_pago": str(f.get("fecha_pago") or ""),
		"estado": "",
		"sales_invoice": "",
		"payment_entry": "",
		"mensaje": "",
	}

	def terminar(estado: str, mensaje: str = "") -> dict[str, Any]:
		reg["estado"] = estado
		if mensaje:
			reg["mensaje"] = mensaje
		return reg

	if es_concepto_carnet(f["concepto"]):
		return terminar("excluido_carnet")
	if not f.get("socio"):
		return terminar("error_socio_no_encontrado")
	if not f.get("fecha_pago"):
		return terminar("error_fecha_invalida")
	medio = map_medio_pago(f.get("medio_pago") or "")
	if not medio:
		return terminar("error_medio_pago_invalido", str(f.get("medio_pago") or ""))
	if flt(f["monto_csv"]) <= 0:
		return terminar("error_monto_invalido")

	periodo = (f["periodo"] or "").strip()
	es_adel = periodo_es_adelantado(periodo, PERIODO_CIERRE)
	if es_adel and not allow_adelantado:
		return terminar("excluido_adelantado")
	if not es_adel and not periodo_leq(periodo, PERIODO_CIERRE):
		return terminar("error_periodo", periodo)

	ref = referencia_informe(
		fila=f["fila"],
		numero_socio=f["nro_socio"] or f["socio"],
		periodo=periodo,
		monto=flt(f["monto_csv"], 2),
		concepto=f["concepto"],
	)
	if _pe_existe_ref(ref) or _pe_existente(f["socio"], ref):
		reg["payment_entry"] = "ya"
		return terminar("ya_imputado")

	item_codes = resolver_item_codes_concepto(
		f["concepto"], socio_name=f["socio"], monto_abonado=flt(f["monto_csv"])
	)
	es_cto = es_cuota_complementaria(f["concepto"])
	if not item_codes and not es_cto:
		return terminar("error_concepto_sin_mapeo")

	match = buscar_linea_factura_concepto(
		f["socio"],
		periodo,
		f["concepto"],
		monto_abonado=flt(f["monto_csv"]),
		reservadas=set(),
		solo_impagas=True,
	)
	invoice_name: str | None = None
	facturada = False
	if match:
		invoice_name, item_code, _line = match
		reg["sales_invoice"] = invoice_name
		reg["item_code"] = item_code
	elif dry_run:
		return terminar("imputado_con_facturacion", "dry-run: facturaría/aplicaría")
	else:
		try:
			if es_cto:
				invoice_name = _facturar_cto_comp(
					f["socio"], periodo, f["concepto"], flt(f["monto_csv"])
				)
			else:
				invoice_name = _emitir_factura_concepto(
					f["socio"],
					periodo,
					f["concepto"],
					item_codes[0],
					monto=flt(f["monto_csv"]),
					mora_pct=0.0,
				)
		except Exception as exc:  # noqa: BLE001
			if not getattr(frappe.flags, "in_test", False):
				frappe.db.rollback()
			return terminar("error_facturacion", str(exc)[:280])
		if not invoice_name:
			return terminar("error_facturacion", "sin SI")
		facturada = True
		reg["sales_invoice"] = invoice_name

	if dry_run:
		return terminar("imputado", "dry-run")

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
			periodo_fila=periodo,
		)
	except Exception as exc:  # noqa: BLE001
		if not getattr(frappe.flags, "in_test", False):
			frappe.db.rollback()
		return terminar("error_cobro", str(exc)[:280])

	pes = result.get("payment_entries") or []
	reg["payment_entry"] = ";".join(pes)
	return terminar("imputado_con_facturacion" if facturada else "imputado")


def reparar_alias_y_adelantados(
	*,
	csv_path: str,
	dry_run: bool = True,
	confirm: str = "",
	commit_every: int = 25,
) -> dict[str, Any]:
	"""Reimputa filas alias (≤08) y facturar+aplica 09/2026 sin PE."""
	from club_management.integrations.payment_ledger_postgres import apply_patch

	apply_patch()
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	frappe.flags.mute_emails = True
	in_test = bool(getattr(frappe.flags, "in_test", False))
	filas = _filas_con_alias(csv_path)

	alias_nros = set(SOCIO_ALIAS_PADRON)
	seleccion: list[dict[str, Any]] = []
	for f in filas:
		nro = (f.get("nro_socio") or "").strip()
		periodo = (f.get("periodo") or "").strip()
		if es_concepto_carnet(f.get("concepto") or ""):
			continue
		if nro in alias_nros and f.get("socio"):
			seleccion.append({**f, "_motivo": "alias"})
		elif periodo_es_adelantado(periodo, PERIODO_CIERRE) and f.get("socio"):
			# Solo 09/2026+ sin PE aún
			ref = referencia_informe(
				fila=f["fila"],
				numero_socio=f["nro_socio"] or f["socio"],
				periodo=periodo,
				monto=flt(f["monto_csv"], 2),
				concepto=f["concepto"],
			)
			if not _pe_existe_ref(ref) and not _pe_existente(f["socio"], ref):
				seleccion.append({**f, "_motivo": "adelantado_09"})

	registros: list[dict[str, Any]] = []
	ok = 0
	for i, f in enumerate(seleccion, start=1):
		allow = f.get("_motivo") == "adelantado_09"
		reg = _procesar_fila_imputacion(f, dry_run=dry_run, allow_adelantado=allow)
		reg["motivo"] = f.get("_motivo")
		registros.append(reg)
		if reg["estado"] in ("imputado", "imputado_con_facturacion", "ya_imputado"):
			ok += 1
		if (
			not dry_run
			and commit_every
			and not in_test
			and ok
			and ok % commit_every == 0
		):
			frappe.db.commit()
			print(f"  imputaciones ok={ok}/{len(seleccion)}")

	if not dry_run and commit_every and not in_test:
		frappe.db.commit()

	por_estado: dict[str, int] = {}
	for r in registros:
		por_estado[r["estado"]] = por_estado.get(r["estado"], 0) + 1

	return {
		"dry_run": dry_run,
		"seleccion_count": len(seleccion),
		"ok_count": ok,
		"por_estado": por_estado,
		"registros": registros,
	}


def run(
	*,
	csv_path: str = CSV_PROD,
	dry_run: bool = True,
	confirm: str = "",
	skip_mora: bool = False,
	skip_imputacion: bool = False,
	commit_every: int = 25,
	out_path: str | None = None,
) -> dict[str, Any]:
	"""Pipeline: mora residual de socios CSV + alias + adelantos 09."""
	_ensure_purge_allowed(dry_run=dry_run, confirm=confirm)
	socios = socios_imputados_desde_csv(csv_path)
	result: dict[str, Any] = {
		"dry_run": dry_run,
		"csv_path": csv_path,
		"socios_imputados": len(socios),
		"aliases": dict(SOCIO_ALIAS_PADRON),
	}

	if not skip_mora:
		print(f"==> Mora residual socios CSV={len(socios)}")
		result["mora"] = cancelar_mora_huerfanas(
			socios=socios,
			dry_run=dry_run,
			confirm=confirm or (CONFIRM_LOCAL if not dry_run else ""),
			commit_every=commit_every,
		)

	if not skip_imputacion:
		print("==> Alias + adelantados 09/2026")
		result["imputacion"] = reparar_alias_y_adelantados(
			csv_path=csv_path,
			dry_run=dry_run,
			confirm=confirm or (CONFIRM_LOCAL if not dry_run else ""),
			commit_every=commit_every,
		)

	destino = Path(out_path or "/tmp/reparar_cierre_migracion_agosto.json")
	destino.write_text(
		json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
	)
	result["out_path"] = str(destino)
	print(f"==> Log: {destino}")
	return result


def run_local(*, dry_run: bool = True) -> dict[str, Any]:
	return run(
		csv_path=CSV_PROD,
		dry_run=dry_run,
		confirm=CONFIRM_LOCAL,
		out_path="/tmp/reparar_cierre_migracion_agosto_local.json",
	)


def run_prod(*, dry_run: bool = True) -> dict[str, Any]:
	return run(
		csv_path=CSV_PROD,
		dry_run=dry_run,
		confirm=CONFIRM_PURGE_PROD,
		out_path="/tmp/reparar_cierre_migracion_agosto_prod.json",
	)
