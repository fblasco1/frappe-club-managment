"""Conciliación de cierre: CSV agosto vs PE INF-* (concepto + equipo/grupo + faltantes).

Spec: `club_management/specs/conciliacion_migracion_agosto.md`

    bench --site SITE execute \\
        club_management.scripts.conciliacion_migracion_agosto.run_prod_agosto
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt, getdate

from club_management.scripts.bulk_io import cell, find_socio, parse_fecha, parse_monto, read_bulk_rows
from club_management.scripts.diagnostico_cobranzas_csv import clasificar_concepto
from club_management.scripts.informe_concepto_cobranza import (
	_ARANCEL_EQUIPO_ALIAS,
	es_concepto_carnet,
	es_cuota_complementaria,
	normalizar_concepto_informe,
	parse_referencia_informe,
	resolver_item_codes_concepto,
)
from club_management.scripts.reparar_cierre_migracion_agosto import resolve_socio_csv

TOLERANCIA = 0.5
BUCKETS_FALTANTE = frozenset(
	{
		"sin_pe_inf",
		"socio_no_encontrado",
		"concepto_sin_mapeo",
	}
)
BUCKETS_OK = frozenset(
	{"ok", "ok_con_mora", "ok_exento_split_indebido", "pe_monto_distinto"}
)



def _clave_match(
	*,
	socio: str,
	periodo: str,
	concepto: str,
	monto: float,
) -> tuple[str, str, str, float]:
	return (
		str(socio or "").strip(),
		str(periodo or "").strip(),
		normalizar_concepto_informe(concepto),
		flt(monto, 2),
	)


def indexar_pe_inf(fecha_desde: str, fecha_hasta: str) -> dict[tuple[str, str, str, float], list[dict[str, Any]]]:
	"""Índice PE INF-* del rango por (socio, periodo, concepto_norm, monto_ref)."""
	index: dict[tuple[str, str, str, float], list[dict[str, Any]]] = defaultdict(list)
	rows = frappe.db.sql(
		"""
		SELECT pe.name, pe.reference_no, pe.paid_amount, pe.posting_date
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
		# socio_ref en la referencia es nro de padrón; resolver a name si existe
		socio_ref = str(parsed["socio_ref"])
		socio_name = frappe.db.exists("Socio", socio_ref) and socio_ref
		if not socio_name:
			found = resolve_socio_csv(socio_ref) or find_socio(nro_socio=socio_ref)
			socio_name = found or socio_ref
		key = _clave_match(
			socio=str(socio_name),
			periodo=str(parsed["periodo"]),
			concepto=str(parsed["concepto"]),
			monto=flt(parsed["monto"], 2),
		)
		index[key].append(
			{
				"pe": row.name,
				"paid_amount": flt(row.paid_amount, 2),
				"posting_date": str(row.posting_date),
				"reference_no": row.reference_no,
				"monto_ref": flt(parsed["monto"], 2),
			}
		)
	return index


def clasificar_fila_vs_pe(
	raw: dict[str, str],
	*,
	pe_index: dict[tuple[str, str, str, float], list[dict[str, Any]]],
	usados: set[str],
) -> dict[str, Any]:
	"""Clasifica una fila CSV contra el índice de PE INF-*."""
	nro = cell(raw, "nro_socio", "numero_socio", "nro")
	concepto = cell(raw, "concepto")
	periodo = cell(raw, "periodo", "periodo_cobro")
	monto = flt(parse_monto(cell(raw, "monto_abonado", "monto")), 2)
	fecha = parse_fecha(cell(raw, "fecha_pago", "fecha"))
	clase = clasificar_concepto(concepto)
	out: dict[str, Any] = {
		"nro_socio": nro,
		"socio": "",
		"fecha_pago": fecha.isoformat() if fecha else "",
		"periodo": periodo,
		"concepto": concepto,
		"concepto_norm": normalizar_concepto_informe(concepto),
		"clase": clase,
		"monto_csv": monto,
		"bucket": "",
		"pe": "",
		"paid_amount": 0.0,
		"gap": monto,
		"item_codes": "",
		"equipo_alias": "",
	}

	if es_concepto_carnet(concepto):
		out["bucket"] = "excluido_carnet"
		out["gap"] = 0.0
		return out

	socio = resolve_socio_csv(nro, dni=cell(raw, "dni"))
	if not socio:
		out["bucket"] = "socio_no_encontrado"
		return out
	out["socio"] = socio

	item_codes = resolver_item_codes_concepto(concepto, socio_name=socio, monto_abonado=monto)
	out["item_codes"] = ";".join(item_codes)
	norm = out["concepto_norm"]
	if norm in _ARANCEL_EQUIPO_ALIAS:
		out["equipo_alias"] = norm

	if not item_codes and not es_cuota_complementaria(concepto):
		out["bucket"] = "concepto_sin_mapeo"
		return out

	# Match exacto por clave; si el monto_ref del INF difiere del paid (mora),
	# también probar con paid_amount del PE vía búsqueda flexible.
	key = _clave_match(socio=socio, periodo=periodo, concepto=concepto, monto=monto)
	candidatos = [c for c in pe_index.get(key, []) if c["pe"] not in usados]

	if not candidatos:
		# Flexible: mismo socio+periodo+concepto, monto ± tolerancia o paid_amount
		norm_c = normalizar_concepto_informe(concepto)
		for k, lista in pe_index.items():
			if k[0] != socio or k[1] != str(periodo).strip() or k[2] != norm_c:
				continue
			for c in lista:
				if c["pe"] in usados:
					continue
				if abs(flt(c["monto_ref"]) - monto) <= TOLERANCIA or abs(flt(c["paid_amount"]) - monto) <= TOLERANCIA:
					candidatos.append(c)
		# dedupe
		seen: set[str] = set()
		uniq = []
		for c in candidatos:
			if c["pe"] in seen:
				continue
			seen.add(c["pe"])
			uniq.append(c)
		candidatos = uniq

	if not candidatos:
		out["bucket"] = "sin_pe_inf"
		return out

	# Consumir el PE más cercano en monto
	candidatos.sort(key=lambda c: abs(flt(c["paid_amount"]) - monto))
	chosen = candidatos[0]
	usados.add(chosen["pe"])
	out["pe"] = chosen["pe"]
	out["paid_amount"] = flt(chosen["paid_amount"], 2)
	out["gap"] = flt(monto - out["paid_amount"], 2)
	if abs(out["gap"]) <= TOLERANCIA:
		out["bucket"] = "ok"
		out["gap"] = 0.0
		return out

	# INF suele ser la base; la mora va en PE aparte ligado al origen.
	from club_management.scripts.alinear_pe_monto_distinto import (
		cobertura_mora_de_pe_inf,
		concepto_exento_mora,
		es_outlier_manual,
	)

	if es_outlier_manual(nro, periodo, concepto):
		out["bucket"] = "pe_monto_distinto"
		return out

	cov = cobertura_mora_de_pe_inf(chosen["pe"], out["gap"])
	paid_total = flt(out["paid_amount"] + flt(cov["suma_mora"]), 2)
	if abs(paid_total - monto) <= TOLERANCIA or cov["cubre"]:
		out["paid_amount"] = paid_total
		out["gap"] = 0.0
		out["pe_mora"] = ";".join(m["pe"] for m in cov["mora_pes"])
		if concepto_exento_mora(concepto):
			out["bucket"] = "ok_exento_split_indebido"
		else:
			out["bucket"] = "ok_con_mora"
		# Marcar PEs mora como usados para no reasignarlos
		for m in cov["mora_pes"]:
			usados.add(m["pe"])
		return out

	out["bucket"] = "pe_monto_distinto"
	return out


def agregar_por_concepto(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
	agg: dict[str, dict[str, Any]] = {}
	for f in filas:
		clave = f.get("concepto_norm") or "(vacío)"
		row = agg.setdefault(
			clave,
			{
				"concepto": clave,
				"clase": f.get("clase") or "",
				"filas_csv": 0,
				"monto_csv": 0.0,
				"filas_ok": 0,
				"monto_pe": 0.0,
				"filas_faltante": 0,
				"monto_faltante": 0.0,
				"filas_error": 0,
				"monto_error": 0.0,
			},
		)
		row["filas_csv"] += 1
		row["monto_csv"] = flt(row["monto_csv"] + flt(f["monto_csv"]), 2)
		bucket = f.get("bucket")
		if bucket in BUCKETS_OK:
			row["filas_ok"] += 1
			row["monto_pe"] = flt(row["monto_pe"] + flt(f["paid_amount"]), 2)
		elif bucket == "sin_pe_inf":
			row["filas_faltante"] += 1
			row["monto_faltante"] = flt(row["monto_faltante"] + flt(f["monto_csv"]), 2)
		elif bucket in ("socio_no_encontrado", "concepto_sin_mapeo"):
			row["filas_error"] += 1
			row["monto_error"] = flt(row["monto_error"] + flt(f["monto_csv"]), 2)
		elif bucket == "excluido_carnet":
			pass
	detalle = []
	for row in agg.values():
		row["gap_csv_menos_pe"] = flt(row["monto_csv"] - row["monto_pe"], 2)
		detalle.append(row)
	detalle.sort(key=lambda r: -abs(flt(r["gap_csv_menos_pe"])))
	return detalle


def agregar_por_equipo_grupo(filas: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Solo conceptos alias de arancel de tira/equipo."""
	agg: dict[str, dict[str, Any]] = {}
	for f in filas:
		alias = f.get("equipo_alias") or ""
		if not alias:
			continue
		row = agg.setdefault(
			alias,
			{
				"equipo_grupo": alias,
				"item_codes": f.get("item_codes") or "",
				"filas_csv": 0,
				"monto_csv": 0.0,
				"filas_ok": 0,
				"monto_pe": 0.0,
				"filas_faltante": 0,
				"monto_faltante": 0.0,
				"filas_error": 0,
				"monto_error": 0.0,
			},
		)
		row["filas_csv"] += 1
		row["monto_csv"] = flt(row["monto_csv"] + flt(f["monto_csv"]), 2)
		bucket = f.get("bucket")
		if bucket in BUCKETS_OK:
			row["filas_ok"] += 1
			row["monto_pe"] = flt(row["monto_pe"] + flt(f["paid_amount"]), 2)
		elif bucket == "sin_pe_inf":
			row["filas_faltante"] += 1
			row["monto_faltante"] = flt(row["monto_faltante"] + flt(f["monto_csv"]), 2)
		elif bucket in ("socio_no_encontrado", "concepto_sin_mapeo"):
			row["filas_error"] += 1
			row["monto_error"] = flt(row["monto_error"] + flt(f["monto_csv"]), 2)
	detalle = []
	for row in agg.values():
		row["gap_csv_menos_pe"] = flt(row["monto_csv"] - row["monto_pe"], 2)
		detalle.append(row)
	detalle.sort(key=lambda r: (-abs(flt(r["gap_csv_menos_pe"])), r["equipo_grupo"]))
	return detalle


def _escribir_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
		writer.writeheader()
		for row in rows:
			writer.writerow({k: row.get(k, "") for k in fields})


def _escribir_log_texto(path: Path, resultado: dict[str, Any]) -> None:
	lines: list[str] = []
	lines.append("=" * 72)
	lines.append(" CONCILIACIÓN MIGRACIÓN AGOSTO 2026")
	lines.append("=" * 72)
	lines.append(f" CSV: {resultado['csv_path']}")
	lines.append(f" Rango PE: {resultado['fecha_desde']} → {resultado['fecha_hasta']}")
	lines.append(f" Filas CSV: {resultado['filas_csv']}")
	lines.append(f" Total CSV: ${resultado['total_csv']:,.2f}")
	lines.append(f" Total PE matched: ${resultado['total_pe_matched']:,.2f}")
	lines.append(f" Gap global (csv-pe matched): ${resultado['gap_global']:,.2f}")
	lines.append("")
	lines.append(" Buckets:")
	for bucket, n in sorted(resultado["buckets"].items(), key=lambda x: -x[1]):
		monto = resultado["montos_por_bucket"].get(bucket, 0)
		lines.append(f"   {bucket:28s} filas={n:5d}  monto=${monto:,.2f}")
	lines.append("")
	lines.append(" Top gaps por concepto (|gap|>0.50):")
	for row in resultado["por_concepto"][:25]:
		if abs(flt(row["gap_csv_menos_pe"])) <= TOLERANCIA:
			continue
		lines.append(
			f"   {row['concepto'][:40]:40s} csv=${row['monto_csv']:12,.2f} "
			f"pe=${row['monto_pe']:12,.2f} gap=${row['gap_csv_menos_pe']:10,.2f} "
			f"falt={row['filas_faltante']} err={row['filas_error']}"
		)
	lines.append("")
	lines.append(" Gaps por equipo/grupo (alias arancel):")
	for row in resultado["por_equipo_grupo"]:
		if abs(flt(row["gap_csv_menos_pe"])) <= TOLERANCIA and row["filas_faltante"] == 0 and row["filas_error"] == 0:
			continue
		lines.append(
			f"   {row['equipo_grupo'][:40]:40s} csv=${row['monto_csv']:12,.2f} "
			f"pe=${row['monto_pe']:12,.2f} gap=${row['gap_csv_menos_pe']:10,.2f} "
			f"falt={row['filas_faltante']} err={row['filas_error']}"
		)
	lines.append("")
	lines.append(f" Faltantes / errores (sin PE / socio / mapeo): {resultado['faltantes_count']}")
	lines.append(
		f" Diferencias de monto CSV vs PE (imputado, mora u otro): "
		f"{resultado.get('diffs_monto_count', 0)} filas / "
		f"${resultado.get('diffs_monto_total', 0):,.2f}"
	)
	lines.append("=" * 72)
	path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
	*,
	csv_path: str,
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	out_dir: str = "/tmp/conciliacion_migracion_agosto",
) -> dict[str, Any]:
	"""Ejecuta conciliación completa y escribe logs en `out_dir`."""
	destino = Path(out_dir)
	destino.mkdir(parents=True, exist_ok=True)

	rows_csv = read_bulk_rows(csv_path)
	pe_index = indexar_pe_inf(fecha_desde, fecha_hasta)
	usados: set[str] = set()
	filas: list[dict[str, Any]] = []
	for raw in rows_csv:
		filas.append(clasificar_fila_vs_pe(raw, pe_index=pe_index, usados=usados))

	from collections import Counter

	buckets = Counter(f["bucket"] for f in filas)
	montos_por_bucket = defaultdict(float)
	for f in filas:
		montos_por_bucket[f["bucket"]] += flt(f["monto_csv"])

	por_concepto = agregar_por_concepto(filas)
	por_equipo = agregar_por_equipo_grupo(filas)

	faltantes = [f for f in filas if f["bucket"] in BUCKETS_FALTANTE]
	faltantes.sort(key=lambda r: (-flt(r["monto_csv"]), r.get("concepto_norm") or "", r.get("nro_socio") or ""))
	diffs_monto = [f for f in filas if f["bucket"] == "pe_monto_distinto"]
	diffs_monto.sort(key=lambda r: -abs(flt(r["gap"])))

	total_csv = flt(sum(flt(f["monto_csv"]) for f in filas), 2)
	total_pe = flt(sum(flt(f["paid_amount"]) for f in filas if f["bucket"] in BUCKETS_OK), 2)

	resultado: dict[str, Any] = {
		"csv_path": csv_path,
		"fecha_desde": fecha_desde,
		"fecha_hasta": fecha_hasta,
		"filas_csv": len(filas),
		"pe_inf_indexados": sum(len(v) for v in pe_index.values()),
		"pe_consumidos": len(usados),
		"total_csv": total_csv,
		"total_pe_matched": total_pe,
		"gap_global": flt(total_csv - total_pe, 2),
		"buckets": dict(buckets),
		"montos_por_bucket": {k: flt(v, 2) for k, v in montos_por_bucket.items()},
		"por_concepto": por_concepto,
		"por_equipo_grupo": por_equipo,
		"faltantes_count": len(faltantes),
		"diffs_monto_count": len(diffs_monto),
		"diffs_monto_total": flt(sum(abs(flt(f["gap"])) for f in diffs_monto), 2),
		"conceptos_con_gap": sum(1 for r in por_concepto if abs(flt(r["gap_csv_menos_pe"])) > TOLERANCIA),
		"equipos_con_gap": sum(1 for r in por_equipo if abs(flt(r["gap_csv_menos_pe"])) > TOLERANCIA),
	}

	_escribir_csv(
		destino / "faltantes_errores.csv",
		faltantes,
		[
			"bucket",
			"nro_socio",
			"socio",
			"fecha_pago",
			"periodo",
			"concepto",
			"clase",
			"monto_csv",
			"paid_amount",
			"gap",
			"pe",
			"item_codes",
			"equipo_alias",
		],
	)
	_escribir_csv(
		destino / "diferencias_monto_csv_vs_pe.csv",
		diffs_monto,
		[
			"nro_socio",
			"socio",
			"fecha_pago",
			"periodo",
			"concepto",
			"clase",
			"monto_csv",
			"paid_amount",
			"gap",
			"pe",
			"equipo_alias",
		],
	)
	_escribir_csv(
		destino / "por_concepto.csv",
		por_concepto,
		[
			"concepto",
			"clase",
			"filas_csv",
			"monto_csv",
			"filas_ok",
			"monto_pe",
			"gap_csv_menos_pe",
			"filas_faltante",
			"monto_faltante",
			"filas_error",
			"monto_error",
		],
	)
	_escribir_csv(
		destino / "por_equipo_grupo.csv",
		por_equipo,
		[
			"equipo_grupo",
			"item_codes",
			"filas_csv",
			"monto_csv",
			"filas_ok",
			"monto_pe",
			"gap_csv_menos_pe",
			"filas_faltante",
			"monto_faltante",
			"filas_error",
			"monto_error",
		],
	)
	_escribir_csv(
		destino / "todas_filas.csv",
		filas,
		[
			"bucket",
			"nro_socio",
			"socio",
			"fecha_pago",
			"periodo",
			"concepto",
			"concepto_norm",
			"clase",
			"monto_csv",
			"paid_amount",
			"gap",
			"pe",
			"item_codes",
			"equipo_alias",
		],
	)
	(destino / "resumen.json").write_text(
		json.dumps(resultado, indent=2, ensure_ascii=False, default=str),
		encoding="utf-8",
	)
	_escribir_log_texto(destino / "conciliacion.log", resultado)
	resultado["out_dir"] = str(destino)
	resultado["log_path"] = str(destino / "conciliacion.log")
	resultado["faltantes_path"] = str(destino / "faltantes_errores.csv")

	print((destino / "conciliacion.log").read_text(encoding="utf-8"))
	return resultado


def run_prod_agosto() -> dict[str, Any]:
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
		out_dir="/tmp/conciliacion_migracion_agosto",
	)


def run_local_agosto() -> dict[str, Any]:
	return run_prod_agosto()
