"""Auditoría y reparación de cobranzas agosto: CSV (verdad) vs producción.

Spec: `club_management/specs/plantilla_carga_cobranzas.md`

bench --site SITE execute club_management.scripts.repair_cobranzas_csv_agosto.audit \\
  --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv"}'

bench --site SITE execute club_management.scripts.repair_cobranzas_csv_agosto.run \\
  --kwargs '{"csv_path": "/tmp/...", "dry_run": false, "confirm": "APPLY_PROD"}'
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
)
from club_management.scripts.bulk_io import cell, find_socio, parse_fecha, parse_monto
from club_management.scripts.bulk_payments import (
	_intentar_cobro_por_concepto,
	map_medio_pago,
	_registrar_cobro_concepto_informe,
)
from club_management.scripts.informe_concepto_cobranza import (
	monto_imputado_concepto_informe_en_rango,
	normalizar_concepto_informe,
	parse_referencia_informe,
	referencia_informe,
)
class RepairStats:
	def __init__(self) -> None:
		self.total_filas = 0
		self.ok = 0
		self.referencias_corregidas = 0
		self.cobros_aplicados = 0
		self.errores: list[dict[str, Any]] = []
		self.discrepancias: list[dict[str, Any]] = []

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"ok": self.ok,
			"referencias_corregidas": self.referencias_corregidas,
			"cobros_aplicados": self.cobros_aplicados,
			"discrepancias": len(self.discrepancias),
			"errores": len(self.errores),
			"detalle_discrepancias": self.discrepancias[:100],
			"detalle_errores": self.errores[:50],
		}


def _load_csv_rows(csv_path: str, fecha_desde: str, fecha_hasta: str) -> list[dict[str, Any]]:
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(f"Archivo no encontrado: {csv_path}")
	rows: list[dict[str, Any]] = []
	with path.open(encoding="utf-8-sig", newline="") as handle:
		for idx, raw in enumerate(csv.DictReader(handle), start=2):
			fecha_raw = cell(raw, "fecha_pago", "fecha")
			fecha = parse_fecha(fecha_raw)
			if not fecha or str(fecha) < fecha_desde or str(fecha) > fecha_hasta:
				continue
			monto = parse_monto(cell(raw, "monto_abonado", "monto"))
			concepto = cell(raw, "concepto")
			periodo = cell(raw, "periodo", "periodo_cobro")
			nro = cell(raw, "nro_socio", "numero_socio", "nro")
			if not nro or not concepto or monto <= 0:
				continue
			rows.append(
				{
					"fila_csv": idx,
					"nro_socio": nro,
					"monto": flt(monto, 2),
					"fecha_pago": str(fecha),
					"medio_pago": cell(raw, "medio_pago", "medio"),
					"periodo": periodo,
					"concepto": concepto,
					"referencia": cell(raw, "referencia_comprobante", "referencia", "comprobante"),
				}
			)
	return rows


def _pes_socio_fecha(socio_name: str, fecha: str) -> list[dict[str, Any]]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	return frappe.db.sql(
		f"""
		SELECT DISTINCT pe.name, pe.reference_no, pe.paid_amount, pe.posting_date
		FROM `tabPayment Entry` pe
		INNER JOIN `tabPayment Entry Reference` per ON per.parent = pe.name
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name
		WHERE pe.docstatus = 1
		  AND pe.posting_date = %s
		  AND si.`{campo_socio}` = %s
		ORDER BY pe.name
		""",
		(getdate(fecha), socio_name),
		as_dict=True,
	)


def _find_pe_para_corregir(
	socio_name: str,
	*,
	fecha: str,
	monto: float,
	periodo: str,
	concepto: str,
) -> dict[str, Any] | None:
	norm = normalizar_concepto_informe(concepto)
	for pe in _pes_socio_fecha(socio_name, fecha):
		parsed = parse_referencia_informe(pe.reference_no)
		if not parsed:
			continue
		if parsed["periodo"] != periodo.strip():
			continue
		if abs(flt(parsed["monto"]) - monto) > 1.0 and abs(flt(pe.paid_amount) - monto) > 1.0:
			continue
		if normalizar_concepto_informe(str(parsed["concepto"])) == norm:
			return {"pe": pe.name, "accion": "ok", "reference_no": pe.reference_no}
		return {
			"pe": pe.name,
			"accion": "corregir_referencia",
			"reference_no": pe.reference_no,
			"concepto_pe": parsed["concepto"],
		}
	for pe in _pes_socio_fecha(socio_name, fecha):
		if abs(flt(pe.paid_amount) - monto) > 1.0:
			continue
		parsed = parse_referencia_informe(pe.reference_no)
		if parsed and parsed["periodo"] == periodo.strip():
			if normalizar_concepto_informe(str(parsed["concepto"])) != norm:
				return {
					"pe": pe.name,
					"accion": "corregir_referencia",
					"reference_no": pe.reference_no,
					"concepto_pe": parsed.get("concepto"),
				}
	return None


def _corregir_referencia_pe(
	pe_name: str,
	*,
	numero_socio: str,
	periodo: str,
	monto: float,
	concepto: str,
	fila_csv: int,
) -> str:
	nueva = referencia_informe(
		fila=fila_csv,
		numero_socio=numero_socio,
		periodo=periodo,
		monto=monto,
		concepto=concepto,
	)
	frappe.db.set_value("Payment Entry", pe_name, "reference_no", nueva, update_modified=False)
	return nueva


def audit(
	csv_path: str = "/tmp/cobranzas_bulk_erp_agosto_2026.csv",
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	*,
	solo_aranceles: bool = False,
	tolerance: float = 1.0,
) -> dict[str, Any]:
	"""Compara cada fila del CSV (fecha cobro en rango) vs imputación en prod."""
	stats = RepairStats()
	for row in _load_csv_rows(csv_path, fecha_desde, fecha_hasta):
		stats.total_filas += 1
		concepto = row["concepto"]
		if solo_aranceles and "CUOTA SOCIAL" in normalizar_concepto_informe(concepto):
			continue
		socio = find_socio(nro_socio=row["nro_socio"])
		if not socio:
			stats.errores.append({**row, "codigo": "socio_no_encontrado"})
			continue
		imputado = monto_imputado_concepto_informe_en_rango(
			socio,
			concepto,
			row["periodo"],
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
		)
		delta = flt(row["monto"] - imputado, 2)
		if abs(delta) <= tolerance:
			stats.ok += 1
			continue
		pe_hint = _find_pe_para_corregir(
			socio,
			fecha=row["fecha_pago"],
			monto=row["monto"],
			periodo=row["periodo"],
			concepto=concepto,
		)
		codigo = "faltante_o_imputacion"
		if pe_hint and pe_hint.get("accion") == "corregir_referencia":
			codigo = "referencia_incorrecta"
		stats.discrepancias.append(
			{
				**row,
				"socio": socio,
				"imputado_sistema": imputado,
				"delta": delta,
				"codigo": codigo,
				"pe_candidato": pe_hint,
			}
		)
	stats.discrepancias.sort(key=lambda r: -abs(flt(r.get("delta"), 2)))
	return stats.to_dict()


def audit_prod_aranceles() -> dict[str, Any]:
	"""Atajo prod: CSV default, solo aranceles."""
	return audit(solo_aranceles=True)


def apply_prod() -> dict[str, Any]:
	"""Atajo prod: aplica reparación agosto."""
	return run(dry_run=False, confirm="APPLY_PROD")


def run(
	csv_path: str = "/tmp/cobranzas_bulk_erp_agosto_2026.csv",
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	*,
	dry_run: bool = True,
	tolerance: float = 1.0,
	limit: int | None = None,
	confirm: str = "",
) -> dict[str, Any]:
	"""Audita y repara: corrige `reference_no` INF y aplica cobros faltantes."""
	if not dry_run and confirm != "APPLY_PROD":
		frappe.throw("Reparación en prod requiere confirm='APPLY_PROD'.")
	if not erpnext_cobranza_disponible():
		frappe.throw("ERPNext no disponible.")

	stats = RepairStats()
	applied = 0
	for row in _load_csv_rows(csv_path, fecha_desde, fecha_hasta):
		if limit is not None and applied >= limit:
			break
		stats.total_filas += 1
		concepto = row["concepto"]
		socio = find_socio(nro_socio=row["nro_socio"])
		if not socio:
			stats.errores.append({**row, "codigo": "socio_no_encontrado"})
			continue

		imputado = monto_imputado_concepto_informe_en_rango(
			socio,
			concepto,
			row["periodo"],
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
		)
		if abs(flt(row["monto"] - imputado)) <= tolerance:
			stats.ok += 1
			continue

		pe_hint = _find_pe_para_corregir(
			socio,
			fecha=row["fecha_pago"],
			monto=row["monto"],
			periodo=row["periodo"],
			concepto=concepto,
		)
		if pe_hint and pe_hint.get("accion") == "corregir_referencia":
			if dry_run:
				stats.referencias_corregidas += 1
				stats.discrepancias.append({**row, "socio": socio, "accion": "corregir_referencia", "pe": pe_hint["pe"]})
				continue
			nueva = _corregir_referencia_pe(
				pe_hint["pe"],
				numero_socio=row["nro_socio"],
				periodo=row["periodo"],
				monto=row["monto"],
				concepto=concepto,
				fila_csv=row["fila_csv"],
			)
			stats.referencias_corregidas += 1
			imputado = monto_imputado_concepto_informe_en_rango(
				socio,
				concepto,
				row["periodo"],
				fecha_desde=fecha_desde,
				fecha_hasta=fecha_hasta,
			)
			if abs(flt(row["monto"] - imputado)) <= tolerance:
				stats.ok += 1
				continue

		# Cobro faltante o mal imputado: aplicar según concepto
		fecha = getdate(row["fecha_pago"])
		medio = map_medio_pago(row["medio_pago"])
		if not medio:
			stats.errores.append({**row, "socio": socio, "codigo": "medio_pago_invalido"})
			continue
		elegidas, exigido, err, item_code = _intentar_cobro_por_concepto(
			socio,
			row["periodo"],
			concepto,
			row["monto"],
			fecha,
			set(),
			tolerance,
		)
		if err or not elegidas:
			stats.errores.append(
				{
					**row,
					"socio": socio,
					"codigo": err or "sin_factura",
					"monto_exigido": exigido,
					"imputado_antes": imputado,
				}
			)
			continue
		ref = row.get("referencia") or referencia_informe(
			fila=row["fila_csv"],
			numero_socio=row["nro_socio"],
			periodo=row["periodo"],
			monto=row["monto"],
			concepto=concepto,
		)
		if dry_run:
			stats.cobros_aplicados += 1
			stats.discrepancias.append(
				{
					**row,
					"socio": socio,
					"accion": "aplicar_cobro",
					"facturas": elegidas,
					"imputado_antes": imputado,
				}
			)
			continue
		try:
			_registrar_cobro_concepto_informe(
				socio,
				elegidas[0],
				row["monto"],
				mode_of_payment=medio,
				posting_date=fecha,
				reference_no=ref,
				auto_submit=True,
				concepto=concepto,
				periodo_fila=row["periodo"],
			)
			stats.cobros_aplicados += 1
			applied += 1
		except frappe.ValidationError as exc:
			stats.errores.append({**row, "socio": socio, "codigo": "error_cobro", "error": str(exc)})

	if not dry_run and applied and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	payload = stats.to_dict()
	payload["dry_run"] = dry_run
	return payload
