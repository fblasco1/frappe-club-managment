"""Diagnóstico read-only del CSV consolidado de cobranzas contra el estado del ERP.

Spec: `club_management/specs/carga_masiva_cobranzas.md`

No crea ni modifica documentos. Mide, para cada fila del CSV, si el concepto resuelve
a un ítem, si existe línea de factura y cuánto está ya imputado en el rango de cobro.

    bench --site dev.localhost execute \\
        club_management.scripts.diagnostico_cobranzas_csv.run \\
        --kwargs '{"csv_path": "/tmp/cobranzas_bulk_erp_agosto_2026.csv"}'
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt

from club_management.members.services.cobranza_manual import SALES_INVOICE_DOCTYPE
from club_management.scripts.bulk_io import cell, find_socio, parse_fecha, parse_monto, read_bulk_rows
from club_management.scripts.informe_concepto_cobranza import (
	buscar_linea_factura_concepto,
	es_cuota_complementaria,
	monto_imputado_concepto_informe_en_rango,
	normalizar_concepto_informe,
	resolver_item_codes_concepto,
)

DIAGNOSTICO_COLUMNAS: tuple[str, ...] = (
	"fila",
	"nro_socio",
	"socio",
	"fecha_pago",
	"periodo",
	"concepto",
	"monto_csv",
	"clase_concepto",
	"item_codes",
	"linea_factura",
	"linea_item_code",
	"linea_monto",
	"linea_outstanding",
	"monto_imputado",
	"bucket",
)


def clasificar_concepto(concepto: str | None) -> str:
	"""Agrupa el concepto del informe en cuota / arancel / federativa / CTO COMP."""
	norm = normalizar_concepto_informe(concepto)
	if not norm:
		return "vacio"
	if es_cuota_complementaria(norm):
		return "cto_comp"
	if "CUOTA SOCIAL" in norm or "CARNET" in norm or norm.startswith("JUBILADO"):
		return "cuota_social"
	if "FED" in norm:
		return "federativa"
	if "FEBAMBA" in norm:
		return "cargo_extra"
	return "arancel"


def _bucket(
	*,
	socio: str | None,
	item_codes: tuple[str, ...],
	clase: str,
	match: tuple[str, str, float] | None,
	outstanding: float,
	imputado: float,
	monto: float,
) -> str:
	if not socio:
		return "socio_no_encontrado"
	if not item_codes and clase != "cto_comp":
		return "concepto_sin_mapeo"
	if abs(imputado - monto) <= 0.5:
		return "ya_imputado"
	if imputado > 0.5:
		return "imputado_parcial"
	if not match:
		return "sin_linea_factura"
	if outstanding <= 0.005:
		return "linea_saldada_sin_imputar"
	return "pendiente_de_cobro"


def _fila_diagnostico(
	idx: int,
	raw: dict[str, str],
	*,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	nro = cell(raw, "nro_socio", "numero_socio", "nro")
	concepto = cell(raw, "concepto")
	periodo = cell(raw, "periodo", "periodo_cobro")
	monto = parse_monto(cell(raw, "monto_abonado", "monto"))
	fecha = parse_fecha(cell(raw, "fecha_pago", "fecha"))
	clase = clasificar_concepto(concepto)

	out: dict[str, Any] = {
		"fila": idx,
		"nro_socio": nro,
		"socio": "",
		"fecha_pago": fecha.isoformat() if fecha else "",
		"periodo": periodo,
		"concepto": concepto,
		"monto_csv": flt(monto, 2),
		"clase_concepto": clase,
		"item_codes": "",
		"linea_factura": "",
		"linea_item_code": "",
		"linea_monto": 0.0,
		"linea_outstanding": 0.0,
		"monto_imputado": 0.0,
		"bucket": "",
	}

	socio = find_socio(nro_socio=nro, dni=cell(raw, "dni"))
	if not socio:
		out["bucket"] = "socio_no_encontrado"
		return out
	out["socio"] = socio

	item_codes = resolver_item_codes_concepto(concepto, socio_name=socio, monto_abonado=monto)
	out["item_codes"] = ";".join(item_codes)

	match = buscar_linea_factura_concepto(
		socio,
		periodo,
		concepto,
		monto_abonado=monto,
		reservadas=set(),
		solo_impagas=False,
	)
	outstanding = 0.0
	if match:
		out["linea_factura"] = match[0]
		out["linea_item_code"] = match[1]
		out["linea_monto"] = flt(match[2], 2)
		outstanding = flt(
			frappe.db.get_value(SALES_INVOICE_DOCTYPE, match[0], "outstanding_amount") or 0,
			2,
		)
		out["linea_outstanding"] = outstanding

	imputado = monto_imputado_concepto_informe_en_rango(
		socio,
		concepto,
		periodo,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
	)
	out["monto_imputado"] = flt(imputado, 2)
	out["bucket"] = _bucket(
		socio=socio,
		item_codes=item_codes,
		clase=clase,
		match=match,
		outstanding=outstanding,
		imputado=imputado,
		monto=monto,
	)
	return out


def run(
	*,
	csv_path: str,
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	out_path: str | None = None,
	limit: int | None = None,
) -> dict[str, Any]:
	"""Diagnóstico read-only: un registro por fila del CSV + resumen por bucket."""
	rows = read_bulk_rows(csv_path)
	destino = Path(out_path or "/tmp/diagnostico_cobranzas.csv")
	registros: list[dict[str, Any]] = []
	for idx, raw in enumerate(rows, start=2):
		if limit is not None and len(registros) >= limit:
			break
		registros.append(
			_fila_diagnostico(idx, raw, fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)
		)

	destino.parent.mkdir(parents=True, exist_ok=True)
	with destino.open("w", encoding="utf-8", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=list(DIAGNOSTICO_COLUMNAS))
		writer.writeheader()
		writer.writerows(registros)

	buckets = Counter(r["bucket"] for r in registros)
	montos_por_bucket = {k: 0.0 for k in buckets}
	for r in registros:
		montos_por_bucket[r["bucket"]] += flt(r["monto_csv"], 2)

	sin_mapeo = sorted(
		{r["concepto"] for r in registros if r["bucket"] == "concepto_sin_mapeo"}
	)
	conceptos_no_resueltos = Counter(
		r["concepto"] for r in registros if not r["item_codes"] and r["clase_concepto"] != "cto_comp"
	)

	resumen = {
		"csv_path": csv_path,
		"out_path": str(destino),
		"filas": len(registros),
		"total_csv": flt(sum(flt(r["monto_csv"], 2) for r in registros), 2),
		"buckets": dict(buckets),
		"montos_por_bucket": {k: flt(v, 2) for k, v in montos_por_bucket.items()},
		"clases": dict(Counter(r["clase_concepto"] for r in registros)),
		"conceptos_sin_mapeo": sin_mapeo,
		"conceptos_no_resueltos": dict(conceptos_no_resueltos),
	}
	resumen_path = destino.with_suffix(".resumen.json")
	resumen_path.write_text(json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8")
	resumen["resumen_path"] = str(resumen_path)
	print(json.dumps(resumen, indent=2, ensure_ascii=False))
	return resumen


def run_prod() -> dict[str, Any]:
	"""Atajo sin kwargs para producción (CSV de agosto 2026 en /tmp)."""
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		out_path="/tmp/diagnostico_agosto_2026.csv",
	)
