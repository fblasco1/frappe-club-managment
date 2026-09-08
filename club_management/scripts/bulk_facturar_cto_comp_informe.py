"""Factura CTO COMP para filas del informe con cargo pendiente y sin SI.

Cruza el Excel de cobranzas (o CSV de inconsistencias) con `Cargo Socio`
pendiente y emite la SI del período vía `prepagar_cargo_socio`.

Spec: `club_management/specs/informe_concepto_cobranza.md`

    bench --site dev.localhost execute club_management.scripts.bulk_facturar_cto_comp_informe.run \\
        --kwargs '{
            "csv_path": "/workspace/backups/.../Cobranza 01 a 28-08.xlsx",
            "dry_run": false,
            "confirm": "local-dev"
        }'
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import frappe
from frappe.exceptions import ValidationError

from club_management.members.services.cargo_extra_prepago import prepagar_cargo_socio
from club_management.members.services.cobranza_manual import (
	cargo_extra_linea_facturada_en_periodo,
	reference_date_desde_periodo,
)
from club_management.scripts.bulk_io import cell, ensure_not_production, find_socio, read_bulk_rows
from club_management.scripts.informe_concepto_cobranza import (
	buscar_cargo_pendiente_cuota_complementaria,
	es_cuota_complementaria,
	necesita_facturacion_cto_comp,
)


def _dedupe_key(socio: str, periodo: str, concepto: str) -> tuple[str, str, str]:
	return (socio, periodo, (concepto or "").strip())


def _filas_desde_inconsistencias(path: Path) -> list[dict[str, str]]:
	rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
	out: list[dict[str, str]] = []
	for row in rows:
		if row.get("codigo") != "sin_factura_impaga":
			continue
		concepto = (row.get("concepto") or "").strip()
		if not es_cuota_complementaria(concepto):
			continue
		socio = (row.get("socio") or row.get("nro_socio") or "").strip()
		periodo = (row.get("periodo") or "").strip()
		if socio and periodo and concepto:
			out.append(
				{
					"socio": socio,
					"periodo": periodo,
					"concepto": concepto,
					"fila": row.get("fila") or "",
				}
			)
	return out


def _filas_desde_informe(path: Path) -> list[dict[str, str]]:
	out: list[dict[str, str]] = []
	for idx, raw in enumerate(read_bulk_rows(str(path)), start=2):
		concepto = cell(raw, "concepto")
		if not es_cuota_complementaria(concepto):
			continue
		periodo = cell(raw, "periodo")
		if not periodo:
			continue
		socio = find_socio(nro_socio=cell(raw, "nro_socio", "numero de socio"), dni=cell(raw, "dni"))
		if not socio:
			continue
		if not necesita_facturacion_cto_comp(socio, periodo, concepto):
			continue
		out.append({"socio": socio, "periodo": periodo, "concepto": concepto, "fila": str(idx)})
	return out


def collect_filas_a_facturar(
	csv_path: str,
	*,
	source: str = "auto",
) -> list[dict[str, str]]:
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(f"Archivo no encontrado: {csv_path}", frappe.DoesNotExistError)

	mode = source
	if mode == "auto":
		if path.suffix.lower() == ".csv" and "inconsistencias" in path.name.lower():
			mode = "inconsistencias"
		else:
			mode = "informe"

	if mode == "inconsistencias":
		rows = _filas_desde_inconsistencias(path)
	else:
		rows = _filas_desde_informe(path)

	seen: set[tuple[str, str, str]] = set()
	unique: list[dict[str, str]] = []
	for row in rows:
		key = _dedupe_key(row["socio"], row["periodo"], row["concepto"])
		if key in seen:
			continue
		seen.add(key)
		unique.append(row)
	return unique


def run(
	*,
	csv_path: str,
	source: str = "auto",
	dry_run: bool = True,
	log_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	ensure_not_production(dry_run=dry_run, confirm=confirm)
	filas = collect_filas_a_facturar(csv_path, source=source)

	facturados: list[dict[str, Any]] = []
	omitidos: list[dict[str, Any]] = []
	sin_cargo: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []

	for idx, fila in enumerate(filas, start=1):
		socio = fila["socio"]
		periodo = fila["periodo"]
		concepto = fila["concepto"]
		entry_base = {**fila}

		cargo = buscar_cargo_pendiente_cuota_complementaria(socio, concepto)
		if not cargo:
			sin_cargo.append({**entry_base, "motivo": "sin_cargo_pendiente"})
			continue

		titulo_cargo = cargo.get("titulo") or ""
		if cargo_extra_linea_facturada_en_periodo(socio, periodo, titulo_cargo):
			omitidos.append(
				{
					**entry_base,
					"cargo": cargo["name"],
					"titulo_cargo": titulo_cargo,
					"motivo": "ya_facturado_periodo",
				}
			)
			continue

		if dry_run:
			facturados.append(
				{
					**entry_base,
					"cargo": cargo["name"],
					"titulo_cargo": titulo_cargo,
					"motivo": "dry_run",
				}
			)
			continue

		try:
			result = prepagar_cargo_socio(
				cargo["name"],
				periodos=[periodo],
				reference_date=reference_date_desde_periodo(periodo),
			)
			created = list(result.get("sales_invoices") or [])
			if created:
				facturados.append(
					{
						**entry_base,
						"cargo": cargo["name"],
						"titulo_cargo": titulo_cargo,
						"sales_invoices": created,
					}
				)
			else:
				skipped = list(result.get("omitidos") or [])
				omitidos.append(
					{
						**entry_base,
						"cargo": cargo["name"],
						"titulo_cargo": titulo_cargo,
						"motivo": "omitido_prepago",
						"periodos": skipped,
					}
				)
		except ValidationError as exc:
			msg = str(exc)
			if "fuera de la vigencia" in msg:
				omitidos.append(
					{
						**entry_base,
						"cargo": cargo["name"],
						"motivo": "periodo_fuera_vigencia",
						"error": msg,
					}
				)
			else:
				errores.append({**entry_base, "cargo": cargo["name"], "error": msg})
		except Exception as exc:
			errores.append({**entry_base, "cargo": cargo["name"], "error": str(exc)})

		if not dry_run and commit_every and idx % commit_every == 0 and not getattr(
			frappe.flags, "in_test", False
		):
			frappe.db.commit()

	if not dry_run and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	payload = {
		"csv_path": csv_path,
		"source": source,
		"dry_run": dry_run,
		"filas_cto_sin_factura": len(filas),
		"facturados": len(facturados),
		"omitidos": len(omitidos),
		"sin_cargo_pendiente": len(sin_cargo),
		"errores": len(errores),
		"detalle_facturados": facturados,
		"detalle_omitidos": omitidos[:150],
		"detalle_sin_cargo": sin_cargo[:150],
		"detalle_errores": errores,
	}
	if log_path:
		path = Path(log_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
		payload["log_path"] = str(path)

	print("\n" + "=" * 72)
	print(f" FACTURAR CTO COMP DESDE INFORME — {'SIMULACIÓN' if dry_run else 'EJECUTADO'}")
	print("=" * 72)
	for k in (
		"filas_cto_sin_factura",
		"facturados",
		"omitidos",
		"sin_cargo_pendiente",
		"errores",
	):
		print(f" {k:30s}: {payload.get(k)}")
	if errores:
		print(" Errores (primeros 5):")
		for err in errores[:5]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
	return payload
