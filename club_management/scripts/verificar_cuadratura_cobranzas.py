"""Verificador de cuadratura del importer consolidado de cobranzas.

Spec: `club_management/specs/carga_masiva_cobranzas.md` («Scenario: cuadratura contable»)

Cruza el CSV de entrada contra el log de auditoría del importer y contra el
total de arancel deportivo cobrado según el sistema (reporte Pagos por equipo).

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.verificar_cuadratura_cobranzas.run_prod_agosto
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from frappe.utils import flt

from club_management.scripts.bulk_io import cell, parse_monto, read_bulk_rows
from club_management.scripts.cobranzas_bulk_importer import ESTADOS_ERROR, ESTADOS_EXCLUIDOS
from club_management.scripts.diagnostico_cobranzas_csv import clasificar_concepto

TOTAL_ESPERADO_AGOSTO_2026 = 52_115_308.00
FILAS_ESPERADAS_AGOSTO_2026 = 2562


def _leer_auditoria(path: str) -> list[dict[str, str]]:
	with Path(path).open(encoding="utf-8", newline="") as handle:
		return list(csv.DictReader(handle))


def run(
	*,
	csv_path: str,
	auditoria_path: str | None = None,
	fecha_desde: str = "2026-08-01",
	fecha_hasta: str = "2026-08-31",
	filas_esperadas: int | None = None,
	total_esperado: float | None = None,
	tolerance: float = 0.5,
) -> dict[str, Any]:
	"""Valida invariantes de no-pérdida y cruza el subtotal de aranceles."""
	rows_csv = read_bulk_rows(csv_path)
	auditoria = _leer_auditoria(auditoria_path or f"{csv_path}.auditoria.csv")

	total_csv = flt(sum(parse_monto(cell(r, "monto_abonado", "monto")) for r in rows_csv), 2)
	total_log = flt(sum(flt(r["monto_csv"]) for r in auditoria), 2)
	total_imputado = flt(
		sum(flt(r["monto_imputado"]) for r in auditoria if r["estado"] != "ya_saldada"), 2
	)
	total_ya_saldado = flt(
		sum(flt(r["monto_csv"]) for r in auditoria if r["estado"] == "ya_saldada"), 2
	)
	total_saldo_favor = flt(sum(flt(r["saldo_favor"]) for r in auditoria), 2)
	total_error = flt(
		sum(flt(r["monto_csv"]) for r in auditoria if r["estado"] in ESTADOS_ERROR), 2
	)
	total_excluido = flt(
		sum(flt(r["monto_csv"]) for r in auditoria if r["estado"] in ESTADOS_EXCLUIDOS), 2
	)

	checks: list[dict[str, Any]] = []

	def check(nombre: str, ok: bool, detalle: str = "") -> None:
		checks.append({"check": nombre, "ok": bool(ok), "detalle": detalle})

	check(
		"filas_log_igual_csv",
		len(auditoria) == len(rows_csv),
		f"log={len(auditoria)} csv={len(rows_csv)}",
	)
	if filas_esperadas is not None:
		check(
			"filas_esperadas",
			len(rows_csv) == filas_esperadas,
			f"csv={len(rows_csv)} esperado={filas_esperadas}",
		)
	check(
		"total_log_igual_csv",
		abs(total_log - total_csv) <= tolerance,
		f"log={total_log} csv={total_csv}",
	)
	if total_esperado is not None:
		check(
			"total_esperado",
			abs(total_csv - flt(total_esperado, 2)) <= tolerance,
			f"csv={total_csv} esperado={flt(total_esperado, 2)}",
		)

	suma_buckets = flt(
		total_imputado + total_saldo_favor + total_ya_saldado + total_error + total_excluido, 2
	)
	gap = flt(total_csv - suma_buckets, 2)
	check(
		"imputado_mas_sf_mas_saldado_mas_error_igual_csv",
		abs(gap) <= tolerance,
		f"imputado={total_imputado} sf={total_saldo_favor} saldado={total_ya_saldado} "
		f"error={total_error} excluido={total_excluido} gap={gap}",
	)

	filas_error = [
		{
			"fila": r["fila"],
			"socio": r["socio"] or r["nro_socio"],
			"concepto": r["concepto"],
			"monto_csv": flt(r["monto_csv"]),
			"estado": r["estado"],
			"mensaje": r["mensaje"],
		}
		for r in auditoria
		if r["estado"] in ESTADOS_ERROR
	]

	# Cruce arancel deportivo: subtotal del CSV vs total del sistema por fecha de PE.
	subtotal_arancel_csv = flt(
		sum(
			parse_monto(cell(r, "monto_abonado", "monto"))
			for r in rows_csv
			if clasificar_concepto(cell(r, "concepto")) == "arancel"
		),
		2,
	)
	from club_management.members.services.liquidacion_equipo import total_arancel_cobrado_en_rango

	arancel_sistema = total_arancel_cobrado_en_rango(fecha_desde, fecha_hasta)
	check(
		"arancel_sistema_cubre_subtotal_csv",
		arancel_sistema >= subtotal_arancel_csv - tolerance,
		f"sistema={arancel_sistema} csv={subtotal_arancel_csv}",
	)

	resultado = {
		"csv_path": csv_path,
		"filas_csv": len(rows_csv),
		"filas_log": len(auditoria),
		"total_csv": total_csv,
		"total_log": total_log,
		"total_imputado": total_imputado,
		"total_ya_saldado": total_ya_saldado,
		"total_saldo_favor": total_saldo_favor,
		"total_error": total_error,
		"total_excluido": total_excluido,
		"subtotal_arancel_csv": subtotal_arancel_csv,
		"arancel_sistema_en_rango": arancel_sistema,
		"checks": checks,
		"ok": all(c["ok"] for c in checks),
		"filas_error": filas_error[:100],
		"filas_error_total": len(filas_error),
	}

	print("\n" + "=" * 72)
	print(" VERIFICADOR DE CUADRATURA")
	print("=" * 72)
	for c in checks:
		print(f" [{'OK' if c['ok'] else 'FALLA'}] {c['check']}: {c['detalle']}")
	print(f" filas en error: {len(filas_error)}")
	print("=" * 72 + "\n")
	out = Path(f"{csv_path}.cuadratura.json")
	out.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
	resultado["cuadratura_path"] = str(out)
	return resultado


def run_prod_agosto() -> dict[str, Any]:
	"""Atajo producción: CSV consolidado de agosto 2026."""
	return run(
		csv_path="/tmp/cobranzas_bulk_erp_agosto_2026.csv",
		fecha_desde="2026-08-01",
		fecha_hasta="2026-08-31",
		filas_esperadas=FILAS_ESPERADAS_AGOSTO_2026,
		total_esperado=TOTAL_ESPERADO_AGOSTO_2026,
	)
