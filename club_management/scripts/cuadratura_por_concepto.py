"""Cuadratura CSV vs sistema agrupada por concepto del informe.

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.cuadratura_por_concepto.run_prod_agosto
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt, getdate

from club_management.members.services.cobranza_manual import SALES_INVOICE_DOCTYPE, _campo_socio_en
from club_management.scripts.bulk_io import cell, parse_monto, read_bulk_rows
from club_management.scripts.cobranzas_bulk_importer import ESTADOS_ERROR, ESTADOS_OK
from club_management.scripts.diagnostico_cobranzas_csv import clasificar_concepto
from club_management.scripts.informe_concepto_cobranza import (
	normalizar_concepto_informe,
	parse_referencia_informe,
)


def _leer_auditoria(path: str) -> list[dict[str, str]]:
	with Path(path).open(encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def _monto_sistema_por_concepto_pe(fecha_desde: str, fecha_hasta: str) -> dict[str, float]:
	"""Suma `paid_amount` de PE agosto con referencia INF- agrupado por concepto parseado."""
	totales: dict[str, float] = defaultdict(float)
	rows = frappe.db.sql(
		"""
		SELECT pe.reference_no, pe.paid_amount
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND pe.posting_date BETWEEN %s AND %s
		  AND pe.reference_no LIKE 'INF-%%'
		""",
		(getdate(fecha_desde), getdate(fecha_hasta)),
		as_dict=True,
	)
	for row in rows:
		parsed = parse_referencia_informe(row.reference_no)
		if not parsed:
			continue
		clave = normalizar_concepto_informe(str(parsed["concepto"]))
		totales[clave] += flt(row.paid_amount, 2)
	return dict(totales)


def run(
	*,
	csv_path: str,
	auditoria_path: str | None = None,
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	out_path: str | None = None,
	top_gap: int = 30,
) -> dict[str, Any]:
	"""Compara totales CSV vs auditoría vs PE del sistema por concepto."""
	rows_csv = read_bulk_rows(csv_path)
	auditoria = _leer_auditoria(auditoria_path or f"{csv_path}.auditoria.csv")
	sistema_pe = _monto_sistema_por_concepto_pe(fecha_desde, fecha_hasta)

	csv_por: dict[str, dict[str, float | int]] = defaultdict(
		lambda: {"filas": 0, "monto_csv": 0.0}
	)
	for raw in rows_csv:
		concepto = cell(raw, "concepto")
		clave = normalizar_concepto_informe(concepto) or "(vacío)"
		csv_por[clave]["filas"] += 1
		csv_por[clave]["monto_csv"] += parse_monto(cell(raw, "monto_abonado", "monto"))

	audit_por: dict[str, dict[str, float | int]] = defaultdict(
		lambda: {
			"filas_ok": 0,
			"filas_error": 0,
			"filas_saldada": 0,
			"monto_imputado_audit": 0.0,
			"monto_saldo_favor": 0.0,
			"monto_error": 0.0,
		}
	)
	for reg in auditoria:
		clave = normalizar_concepto_informe(reg["concepto"]) or "(vacío)"
		estado = reg["estado"]
		monto = flt(reg["monto_csv"])
		if estado in ESTADOS_ERROR:
			audit_por[clave]["filas_error"] += 1
			audit_por[clave]["monto_error"] += monto
		elif estado == "ya_saldada":
			audit_por[clave]["filas_saldada"] += 1
			audit_por[clave]["monto_imputado_audit"] += flt(reg["monto_imputado"])
		elif estado in ESTADOS_OK:
			audit_por[clave]["filas_ok"] += 1
			audit_por[clave]["monto_imputado_audit"] += flt(reg["monto_imputado"])
			audit_por[clave]["monto_saldo_favor"] += flt(reg["saldo_favor"])

	detalle: list[dict[str, Any]] = []
	claves = sorted(set(csv_por) | set(audit_por) | set(sistema_pe))
	for clave in claves:
		c = csv_por.get(clave, {})
		a = audit_por.get(clave, {})
		monto_csv = flt(c.get("monto_csv"), 2)
		monto_audit = flt(a.get("monto_imputado_audit"), 2)
		monto_sf = flt(a.get("monto_saldo_favor"), 2)
		monto_sistema = flt(sistema_pe.get(clave), 2)
		gap_csv_sistema = flt(monto_csv - monto_sistema, 2)
		detalle.append(
			{
				"concepto": clave,
				"clase": clasificar_concepto(clave),
				"filas_csv": int(c.get("filas") or 0),
				"monto_csv": monto_csv,
				"filas_ok_audit": int(a.get("filas_ok") or 0),
				"filas_saldada_audit": int(a.get("filas_saldada") or 0),
				"filas_error_audit": int(a.get("filas_error") or 0),
				"monto_imputado_audit": monto_audit,
				"monto_saldo_favor": monto_sf,
				"monto_error": flt(a.get("monto_error"), 2),
				"monto_pe_sistema": monto_sistema,
				"gap_csv_menos_sistema": gap_csv_sistema,
			}
		)

	detalle.sort(key=lambda r: -abs(flt(r["gap_csv_menos_sistema"])))
	gaps = [r for r in detalle if abs(flt(r["gap_csv_menos_sistema"])) > 0.5]

	resumen_clase: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
	for row in detalle:
		clase = row["clase"]
		resumen_clase[clase]["monto_csv"] += flt(row["monto_csv"])
		resumen_clase[clase]["monto_pe_sistema"] += flt(row["monto_pe_sistema"])
		resumen_clase[clase]["monto_error"] += flt(row["monto_error"])

	resultado = {
		"csv_path": csv_path,
		"fecha_desde": fecha_desde,
		"fecha_hasta": fecha_hasta,
		"total_csv": flt(sum(r["monto_csv"] for r in detalle), 2),
		"total_pe_sistema": flt(sum(sistema_pe.values()), 2),
		"total_error_audit": flt(sum(a.get("monto_error", 0) for a in audit_por.values()), 2),
		"conceptos_con_gap": len(gaps),
		"resumen_por_clase": {k: dict(v) for k, v in resumen_clase.items()},
		"top_gaps": detalle[:top_gap],
		"detalle": detalle,
	}

	destino = Path(out_path or f"{csv_path}.cuadratura_conceptos.json")
	destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
	resultado["out_path"] = str(destino)

	# CSV legible
	csv_out = Path(str(destino).replace(".json", ".csv"))
	with csv_out.open("w", encoding="utf-8", newline="") as handle:
		fields = [
			"concepto",
			"clase",
			"filas_csv",
			"monto_csv",
			"monto_pe_sistema",
			"gap_csv_menos_sistema",
			"monto_imputado_audit",
			"monto_error",
			"filas_error_audit",
		]
		writer = csv.DictWriter(handle, fieldnames=fields)
		writer.writeheader()
		for row in sorted(detalle, key=lambda r: r["concepto"]):
			writer.writerow({k: row.get(k, "") for k in fields})
	resultado["csv_path_out"] = str(csv_out)

	print("\n" + "=" * 72)
	print(" CUADRATURA POR CONCEPTO")
	print("=" * 72)
	print(f" total CSV: {resultado['total_csv']:,.2f}")
	print(f" total PE sistema (INF agosto): {resultado['total_pe_sistema']:,.2f}")
	print(f" total en error (audit): {resultado['total_error_audit']:,.2f}")
	print(" por clase:")
	for clase, vals in sorted(resultado["resumen_por_clase"].items()):
		gap = flt(vals["monto_csv"] - vals["monto_pe_sistema"], 2)
		print(
			f"   {clase:14s} csv={vals['monto_csv']:12,.0f}  sistema={vals['monto_pe_sistema']:12,.0f}  gap={gap:,.0f}"
		)
	print(f" conceptos con gap > $0.50: {resultado['conceptos_con_gap']}")
	print("=" * 72 + "\n")
	return resultado


def run_prod_agosto() -> dict[str, Any]:
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
	)
