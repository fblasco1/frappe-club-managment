"""Alta masiva de `Cargo Socio` CTO COMP desde informe + facturar + apply.

Spec: `club_management/specs/informe_concepto_cobranza.md`

    bench --site dev.localhost execute club_management.scripts.bulk_alta_cargo_cto_comp_informe.run_pipeline \\
        --kwargs '{
            "csv_path": "/workspace/backups/.../Cobranza 01 a 28-08.xlsx",
            "dry_run": false,
            "confirm": "local-dev"
        }'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import flt

from club_management.members.services.cargo_socio import crear_cargo_extra_socio
from club_management.members.services.cobranza_manual import reference_date_desde_periodo
from club_management.scripts.bulk_facturar_cto_comp_informe import run as run_facturar_cto_comp
from club_management.scripts.bulk_io import cell, ensure_not_production, find_socio, parse_monto, read_bulk_rows
from club_management.scripts.informe_concepto_cobranza import (
	ITEM_CUOTA_COMPLEMENTARIA,
	buscar_cargo_socio_cuota_complementaria,
	es_cuota_complementaria,
	necesita_alta_cargo_cto_comp,
	normalizar_clave_cuota_complementaria,
)

DEFAULT_FECHA_HASTA = "2026-12-31"
TIPO_CARGO = "Otro"
MODO_COBRO = "Recurrente"


def _periodo_sort_key(periodo: str) -> tuple[int, int]:
	parts = (periodo or "").split("/")
	if len(parts) != 2:
		return (9999, 99)
	try:
		return (int(parts[1]), int(parts[0]))
	except ValueError:
		return (9999, 99)


def collect_filas_alta_cargo(csv_path: str) -> list[dict[str, Any]]:
	"""Filas únicas (socio + concepto) que requieren alta de cargo."""
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(f"Archivo no encontrado: {csv_path}", frappe.DoesNotExistError)

	merged: dict[tuple[str, str], dict[str, Any]] = {}
	for idx, raw in enumerate(read_bulk_rows(str(path)), start=2):
		concepto = cell(raw, "concepto").strip()
		if not es_cuota_complementaria(concepto):
			continue
		periodo = cell(raw, "periodo").strip()
		if not periodo:
			continue
		monto = parse_monto(cell(raw, "monto_abonado", "monto"))
		if monto <= 0:
			continue
		socio = find_socio(
			nro_socio=cell(raw, "nro_socio", "numero de socio"),
			dni=cell(raw, "dni"),
		)
		if not socio:
			continue
		if not necesita_alta_cargo_cto_comp(socio, periodo, concepto):
			continue

		clave = normalizar_clave_cuota_complementaria(concepto)
		key = (socio, clave)
		entry = merged.get(key)
		if not entry:
			merged[key] = {
				"socio": socio,
				"concepto": concepto,
				"titulo": concepto,
				"monto": monto,
				"periodos": [periodo],
				"filas": [str(idx)],
			}
			continue
		if periodo not in entry["periodos"]:
			entry["periodos"].append(periodo)
		entry["filas"].append(str(idx))
		if abs(flt(entry["monto"]) - monto) > 1.0:
			entry["monto"] = max(flt(entry["monto"]), monto)

	for entry in merged.values():
		entry["periodos"] = sorted(entry["periodos"], key=_periodo_sort_key)
		primero = entry["periodos"][0]
		entry["fecha_desde"] = str(reference_date_desde_periodo(primero))
	return list(merged.values())


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	fecha_hasta: str = DEFAULT_FECHA_HASTA,
	log_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	ensure_not_production(dry_run=dry_run, confirm=confirm)
	filas = collect_filas_alta_cargo(csv_path)

	creados: list[dict[str, Any]] = []
	omitidos: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []

	for idx, fila in enumerate(filas, start=1):
		socio = fila["socio"]
		concepto = fila["concepto"]
		entry_base = {
			"socio": socio,
			"concepto": concepto,
			"monto": fila["monto"],
			"periodos": fila["periodos"],
			"filas": fila.get("filas"),
		}
		if buscar_cargo_socio_cuota_complementaria(socio, concepto):
			omitidos.append({**entry_base, "motivo": "cargo_ya_existe"})
			continue
		if dry_run:
			creados.append({**entry_base, "motivo": "dry_run"})
			continue
		try:
			result = crear_cargo_extra_socio(
				socio=socio,
				titulo=fila["titulo"],
				tipo_cargo=TIPO_CARGO,
				modo_cobro=MODO_COBRO,
				item=ITEM_CUOTA_COMPLEMENTARIA,
				monto=flt(fila["monto"]),
				fecha_desde=fila["fecha_desde"],
				fecha_hasta=fecha_hasta,
				observaciones="Alta masiva desde informe de cobranzas",
				facturar_mes_corriente=False,
			)
			creados.append({**entry_base, "cargo": result.get("cargo"), "estado": result.get("estado")})
		except Exception as exc:
			errores.append({**entry_base, "error": str(exc)})

		if not dry_run and commit_every and idx % commit_every == 0 and not getattr(
			frappe.flags, "in_test", False
		):
			frappe.db.commit()

	if not dry_run and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	payload = {
		"csv_path": csv_path,
		"dry_run": dry_run,
		"filas_alta": len(filas),
		"creados": len(creados),
		"omitidos": len(omitidos),
		"errores": len(errores),
		"detalle_creados": creados[:200],
		"detalle_omitidos": omitidos[:50],
		"detalle_errores": errores,
	}
	if log_path:
		path = Path(log_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
		payload["log_path"] = str(path)

	print("\n" + "=" * 72)
	print(f" ALTA MASIVA CARGO CTO COMP — {'SIMULACIÓN' if dry_run else 'EJECUTADO'}")
	print("=" * 72)
	for k in ("filas_alta", "creados", "omitidos", "errores"):
		print(f" {k:30s}: {payload.get(k)}")
	if errores:
		print(" Errores (primeros 5):")
		for err in errores[:5]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
	return payload


def run_pipeline(
	*,
	csv_path: str,
	dry_run: bool = True,
	tolerance: float = 1.0,
	log_dir: str | None = None,
	confirm: str = "",
) -> dict[str, Any]:
	"""Alta → facturar CTO COMP → apply cobranzas."""
	base = Path(log_dir or "/workspace/backups/prod-to-local/imports")
	alta = run(
		csv_path=csv_path,
		dry_run=dry_run,
		log_path=str(base / "alta_cargo_cto_comp.json"),
		confirm=confirm,
	)
	facturar = run_facturar_cto_comp(
		csv_path=csv_path,
		source="informe",
		dry_run=dry_run,
		log_path=str(base / "facturar_cto_comp_post_alta.json"),
		confirm=confirm,
	)
	from club_management.scripts.bulk_payments import run as run_apply

	apply = run_apply(
		csv_path=csv_path,
		dry_run=dry_run,
		tolerance=tolerance,
		log_path=str(base / "apply_cobranzas_post_alta.json"),
		confirm=confirm,
	)
	return {"alta": alta, "facturar": facturar, "apply": apply}
