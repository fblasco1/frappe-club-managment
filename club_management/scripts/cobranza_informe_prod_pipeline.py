"""Pipeline apply cobranza informe Excel (local `local-dev` / prod `APPLY_PROD`).

Spec: `club_management/specs/carga_masiva_cobranzas.md`

Orden (réplica del cierre validado en dev.localhost):

1. Parche tarifas cuota impagas
2. Sync PLE cuota social
3. Refacturas puntuales del informe
4. Alta cargo CTO COMP
5. Facturar CTO COMP
6. Facturar cuota complementaria pendiente
7. Dry-run apply → detectar sin_factura
8. Facturar sin_factura (desde CSV inconsistencias)
9. Dry-run apply (control)
10. Apply cobranzas (si `dry_run=False`)

    bench --site gestion.icdpedroechague.com.ar execute \\
        club_management.scripts.cobranza_informe_prod_pipeline.run \\
        --kwargs '{
            "csv_path": "/tmp/Cobranza 01 a 28-08.xlsx",
            "dry_run": true,
            "log_dir": "/tmp/cobranza_pipeline"
        }'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe

from club_management.ops.consolidate_cuota_social_item import run_sync_ple
from club_management.scripts.bulk_alta_cargo_cto_comp_informe import run as run_alta_cargo
from club_management.scripts.bulk_facturar_cto_comp_informe import run as run_facturar_cto
from club_management.scripts.bulk_facturar_cuota_complementaria import run as run_facturar_cuota_comp
from club_management.scripts.bulk_facturar_sin_factura_informe import run as run_facturar_sin_factura
from club_management.scripts.bulk_io import ensure_bulk_apply_allowed
from club_management.scripts.bulk_payments import run as run_bulk_payments
from club_management.scripts.fix_refactura_items_informe import run as run_fix_refactura
from club_management.scripts.fix_tarifas_cuota_impagas import run as run_fix_tarifas

DEFAULT_PERIODOS_CTO = ("08/2026", "07/2026")


def _log_path(log_dir: Path, name: str) -> str:
	return str(log_dir / name)


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	tolerance: float = 1.0,
	log_dir: str = "/tmp/cobranza_pipeline",
	confirm: str = "",
	periodos_cto_comp: list[str] | None = None,
	skip_apply: bool = False,
) -> dict[str, Any]:
	"""Ejecuta el pipeline completo. `dry_run=True` simula todos los pasos."""
	step_dry = dry_run
	if not dry_run:
		ensure_bulk_apply_allowed(dry_run=False, confirm=confirm)

	base = Path(log_dir)
	base.mkdir(parents=True, exist_ok=True)
	periodos = list(periodos_cto_comp or DEFAULT_PERIODOS_CTO)
	sub_confirm = confirm if not dry_run else ""

	results: dict[str, Any] = {"csv_path": csv_path, "dry_run": dry_run, "skip_apply": skip_apply}

	results["fix_tarifas"] = run_fix_tarifas(dry_run=step_dry, confirm=sub_confirm)

	results["sync_ple"] = run_sync_ple(dry_run=step_dry, confirm=sub_confirm)

	results["fix_refactura"] = run_fix_refactura(dry_run=step_dry, confirm=sub_confirm)

	results["alta_cargo_cto"] = run_alta_cargo(
		csv_path=csv_path,
		dry_run=step_dry,
		confirm=sub_confirm,
		log_path=_log_path(base, "alta_cargo_cto_comp.json"),
	)

	results["facturar_cto"] = run_facturar_cto(
		csv_path=csv_path,
		source="informe",
		dry_run=step_dry,
		confirm=sub_confirm,
		log_path=_log_path(base, "facturar_cto_comp.json"),
	)

	results["facturar_cuota_comp"] = run_facturar_cuota_comp(
		periodos=periodos,
		dry_run=step_dry,
		confirm=sub_confirm,
		log_path=_log_path(base, "facturar_cuota_comp.json"),
	)

	apply_dry_log = _log_path(base, "apply_dry.json")
	results["apply_dry_1"] = run_bulk_payments(
		csv_path=csv_path,
		dry_run=True,
		tolerance=tolerance,
		log_path=apply_dry_log,
	)

	inc_csv = str(Path(apply_dry_log).with_suffix(".inconsistencias.csv"))
	if Path(inc_csv).is_file():
		results["facturar_sin_factura"] = run_facturar_sin_factura(
			csv_path=inc_csv,
			source="inconsistencias",
			dry_run=step_dry,
			confirm=sub_confirm,
			log_path=_log_path(base, "facturar_sin_factura.json"),
		)
	else:
		results["facturar_sin_factura"] = {"skipped": True, "reason": "sin_csv_inconsistencias"}

	apply_dry2_log = _log_path(base, "apply_dry_2.json")
	results["apply_dry_2"] = run_bulk_payments(
		csv_path=csv_path,
		dry_run=True,
		tolerance=tolerance,
		log_path=apply_dry2_log,
	)

	if dry_run or skip_apply:
		results["apply"] = {"skipped": True, "reason": "dry_run_or_skip_apply"}
	else:
		ensure_bulk_apply_allowed(dry_run=False, confirm=confirm)
		results["apply"] = run_bulk_payments(
			csv_path=csv_path,
			dry_run=False,
			tolerance=tolerance,
			confirm=confirm,
			log_path=_log_path(base, "apply_prod.json"),
		)

	summary_path = base / "pipeline_summary.json"
	summary_path.write_text(
		json.dumps(results, indent=2, ensure_ascii=False, default=str),
		encoding="utf-8",
	)
	results["summary_path"] = str(summary_path)
	_print_resumen(results)
	return results


def _print_resumen(results: dict[str, Any]) -> None:
	print("\n" + "=" * 72)
	print(" PIPELINE COBRANZA INFORME")
	print("=" * 72)
	for key in (
		"fix_tarifas",
		"sync_ple",
		"fix_refactura",
		"alta_cargo_cto",
		"facturar_cto",
		"facturar_cuota_comp",
		"apply_dry_1",
		"facturar_sin_factura",
		"apply_dry_2",
		"apply",
	):
		block = results.get(key) or {}
		if isinstance(block, dict) and block.get("skipped"):
			print(f" {key:24s}: omitido ({block.get('reason')})")
			continue
		if key.startswith("apply"):
			inc = len((block or {}).get("inconsistencias") or [])
			proc = (block or {}).get("procesadas")
			print(f" {key:24s}: procesadas={proc} inconsistencias={inc}")
		elif key == "fix_tarifas":
			print(
				f" {key:24s}: parcheadas={(block or {}).get('parcheadas')} "
				f"sin_cambio={(block or {}).get('sin_cambio')}"
			)
		elif key == "sync_ple":
			print(f" {key:24s}: fixed={(block or {}).get('fixed_count')}")
		else:
			print(f" {key:24s}: ok")
	print(f" Resumen JSON: {results.get('summary_path')}")
	print("=" * 72 + "\n")
