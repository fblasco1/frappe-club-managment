"""Factura cuota/aranceles/federativas para filas `sin_factura_impaga` (no CTO COMP).

Usa `generar_cargo_socio` por socio/período y, si falta la línea del concepto,
emite una SI puntual con el ítem resuelto desde el informe.

Spec: `club_management/specs/informe_concepto_cobranza.md`

    bench --site dev.localhost execute club_management.scripts.bulk_facturar_sin_factura_informe.run \\
        --kwargs '{
            "csv_path": "/workspace/backups/.../apply_cobranzas_v8.inconsistencias.csv",
            "source": "inconsistencias",
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
from frappe.utils import flt

from club_management.members.services.cobranza_manual import (
	_campo_socio_en,
	_default_company,
	ensure_customer_for_socio,
	generar_cargo_socio,
	get_club_settings,
	reference_date_desde_periodo,
	resolve_cost_center_item,
)
from club_management.members.services.cobranza_periodica import resolve_fechas_factura_mensual
from club_management.scripts.bulk_io import cell, ensure_not_production, find_socio, parse_monto, read_bulk_rows
from club_management.scripts.informe_concepto_cobranza import (
	buscar_linea_factura_concepto,
	es_cuota_complementaria,
	resolver_item_codes_concepto,
)


def _dedupe_key(socio: str, periodo: str, concepto: str) -> tuple[str, str, str]:
	return (socio, periodo, (concepto or "").strip())


def _filas_desde_inconsistencias(path: Path) -> list[dict[str, Any]]:
	rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
	out: list[dict[str, Any]] = []
	for row in rows:
		if row.get("codigo") != "sin_factura_impaga":
			continue
		concepto = (row.get("concepto") or "").strip()
		if es_cuota_complementaria(concepto):
			continue
		socio = (row.get("socio") or row.get("nro_socio") or "").strip()
		periodo = (row.get("periodo") or "").strip()
		monto = flt(row.get("monto_abonado") or row.get("monto") or 0)
		if socio and periodo and concepto:
			out.append(
				{
					"socio": socio,
					"periodo": periodo,
					"concepto": concepto,
					"monto": monto,
					"fila": row.get("fila") or "",
				}
			)
	return out


def _filas_desde_apply_json(path: Path) -> list[dict[str, Any]]:
	data = json.loads(path.read_text(encoding="utf-8"))
	out: list[dict[str, Any]] = []
	for row in data.get("inconsistencias") or []:
		if row.get("codigo") != "sin_factura_impaga":
			continue
		concepto = (row.get("concepto") or "").strip()
		if es_cuota_complementaria(concepto):
			continue
		socio = (row.get("socio") or row.get("nro_socio") or "").strip()
		periodo = (row.get("periodo") or "").strip()
		monto = flt(row.get("monto_abonado") or 0)
		if socio and periodo and concepto:
			out.append(
				{
					"socio": socio,
					"periodo": periodo,
					"concepto": concepto,
					"monto": monto,
					"fila": row.get("fila") or "",
				}
			)
	return out


def _filas_desde_informe(path: Path) -> list[dict[str, Any]]:
	from club_management.scripts.bulk_payments import facturas_periodo

	out: list[dict[str, Any]] = []
	for idx, raw in enumerate(read_bulk_rows(str(path)), start=2):
		concepto = cell(raw, "concepto").strip()
		if not concepto or es_cuota_complementaria(concepto):
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
		if buscar_linea_factura_concepto(socio, periodo, concepto, monto_abonado=monto):
			continue
		if facturas_periodo(socio, periodo):
			continue
		out.append(
			{
				"socio": socio,
				"periodo": periodo,
				"concepto": concepto,
				"monto": monto,
				"fila": str(idx),
			}
		)
	return out


def collect_filas_a_facturar(
	csv_path: str,
	*,
	source: str = "auto",
) -> list[dict[str, Any]]:
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(f"Archivo no encontrado: {csv_path}", frappe.DoesNotExistError)

	mode = source
	if mode == "auto":
		if path.suffix.lower() == ".json" and "apply_cobranzas" in path.name.lower():
			mode = "apply_json"
		elif path.suffix.lower() == ".csv" and "inconsistencias" in path.name.lower():
			mode = "inconsistencias"
		else:
			mode = "informe"

	if mode == "apply_json":
		rows = _filas_desde_apply_json(path)
	elif mode == "inconsistencias":
		rows = _filas_desde_inconsistencias(path)
	else:
		rows = _filas_desde_informe(path)

	seen: set[tuple[str, str, str]] = set()
	unique: list[dict[str, Any]] = []
	for row in rows:
		key = _dedupe_key(row["socio"], row["periodo"], row["concepto"])
		if key in seen:
			continue
		seen.add(key)
		unique.append(row)
	return unique


def _emitir_linea_concepto(
	socio: str,
	periodo: str,
	concepto: str,
	*,
	monto_informe: float,
) -> str | None:
	"""Emite SI de una línea cuando `generar_cargo_socio` no incluyó el concepto."""
	from club_management.members.services.cobranza_manual import _submit_sales_invoice_concepto

	if buscar_linea_factura_concepto(socio, periodo, concepto, monto_abonado=monto_informe):
		return None

	item_codes = resolver_item_codes_concepto(concepto, socio_name=socio)
	if not item_codes:
		return None
	item_code = item_codes[0]
	rate = flt(monto_informe)
	if rate <= 0:
		rate = flt(frappe.db.get_value("Item", item_code, "standard_rate"))
	if rate <= 0:
		return None

	campo_socio = _campo_socio_en("Sales Invoice")
	if not campo_socio:
		return None
	customer = ensure_customer_for_socio(socio, skip_permission_check=True)
	ref = reference_date_desde_periodo(periodo)
	posting, due = resolve_fechas_factura_mensual(
		ref,
		int(get_club_settings().dia_primer_vencimiento or 10),
	)
	company = _default_company()
	linea: dict[str, Any] = {
		"item_code": item_code,
		"qty": 1,
		"rate": rate,
		"description": concepto,
	}
	cost_center = resolve_cost_center_item(item_code, company)
	if cost_center:
		linea["cost_center"] = cost_center

	return _submit_sales_invoice_concepto(
		socio_name=socio,
		customer=customer,
		campo_socio=campo_socio,
		periodo=periodo,
		posting=posting,
		due=due,
		item=linea,
	)


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

	periodos_por_socio: dict[tuple[str, str], list[dict[str, Any]]] = {}
	for fila in filas:
		key = (fila["socio"], fila["periodo"])
		periodos_por_socio.setdefault(key, []).append(fila)

	facturados_periodo: list[dict[str, Any]] = []
	facturados_linea: list[dict[str, Any]] = []
	omitidos: list[dict[str, Any]] = []
	sin_resolucion: list[dict[str, Any]] = []
	errores: list[dict[str, Any]] = []

	for idx, ((socio, periodo), grupo) in enumerate(sorted(periodos_por_socio.items()), start=1):
		entry_base = {"socio": socio, "periodo": periodo, "conceptos": [g["concepto"] for g in grupo]}
		ref = reference_date_desde_periodo(periodo)

		if dry_run:
			facturados_periodo.append({**entry_base, "motivo": "dry_run_generar_cargo_socio"})
			continue

		try:
			created = generar_cargo_socio(socio, reference_date=ref)
			if created:
				facturados_periodo.append({**entry_base, "sales_invoices": created})
			else:
				omitidos.append({**entry_base, "motivo": "sin_conceptos_pendientes"})
		except ValidationError as exc:
			msg = str(exc)
			if "No hay conceptos pendientes" in msg or "ya cargados" in msg:
				omitidos.append({**entry_base, "motivo": "sin_conceptos_pendientes", "detalle": msg})
			else:
				errores.append({**entry_base, "error": msg})
		except Exception as exc:
			errores.append({**entry_base, "error": str(exc)})

		if not dry_run and commit_every and idx % commit_every == 0 and not getattr(
			frappe.flags, "in_test", False
		):
			frappe.db.commit()

	# Segunda pasada: líneas puntuales (p. ej. federativa) no incluidas en deuda mensual.
	for fila in filas:
		socio = fila["socio"]
		periodo = fila["periodo"]
		concepto = fila["concepto"]
		monto = flt(fila.get("monto"))
		entry_base = {**fila}

		if buscar_linea_factura_concepto(socio, periodo, concepto, monto_abonado=monto):
			omitidos.append({**entry_base, "motivo": "linea_ya_existe"})
			continue

		if dry_run:
			item_codes = resolver_item_codes_concepto(concepto, socio_name=socio)
			if item_codes:
				facturados_linea.append({**entry_base, "motivo": "dry_run_linea", "item_code": item_codes[0]})
			else:
				sin_resolucion.append({**entry_base, "motivo": "sin_item_code"})
			continue

		try:
			invoice_name = _emitir_linea_concepto(
				socio,
				periodo,
				concepto,
				monto_informe=monto,
			)
			if invoice_name:
				facturados_linea.append({**entry_base, "sales_invoice": invoice_name})
			else:
				sin_resolucion.append({**entry_base, "motivo": "sin_linea_emitida"})
		except Exception as exc:
			errores.append({**entry_base, "error": str(exc)})

	if not dry_run and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	payload = {
		"csv_path": csv_path,
		"source": source,
		"dry_run": dry_run,
		"filas_sin_factura": len(filas),
		"socios_periodos": len(periodos_por_socio),
		"facturados_periodo": len(facturados_periodo),
		"facturados_linea": len(facturados_linea),
		"omitidos": len(omitidos),
		"sin_resolucion": len(sin_resolucion),
		"errores": len(errores),
		"detalle_facturados_periodo": facturados_periodo,
		"detalle_facturados_linea": facturados_linea,
		"detalle_omitidos": omitidos[:150],
		"detalle_sin_resolucion": sin_resolucion,
		"detalle_errores": errores,
	}
	if log_path:
		path = Path(log_path)
		path.parent.mkdir(parents=True, exist_ok=True)
		path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
		payload["log_path"] = str(path)

	print("\n" + "=" * 72)
	print(f" FACTURAR SIN FACTURA (NO CTO COMP) — {'SIMULACIÓN' if dry_run else 'EJECUTADO'}")
	print("=" * 72)
	for k in (
		"filas_sin_factura",
		"socios_periodos",
		"facturados_periodo",
		"facturados_linea",
		"omitidos",
		"sin_resolucion",
		"errores",
	):
		print(f" {k:30s}: {payload.get(k)}")
	if sin_resolucion:
		print(" Sin resolución (primeros 5):")
		for row in sin_resolucion[:5]:
			print(f"   - {row}")
	if errores:
		print(" Errores (primeros 5):")
		for err in errores[:5]:
			print(f"   - {err}")
	print("=" * 72 + "\n")
	return payload


def run_pipeline(
	*,
	csv_path: str,
	source: str = "auto",
	dry_run: bool = True,
	tolerance: float = 1.0,
	log_dir: str | None = None,
	confirm: str = "",
) -> dict[str, Any]:
	"""Factura pendientes + apply cobranzas."""
	base = Path(log_dir or "/workspace/backups/prod-to-local/imports")
	facturar = run(
		csv_path=csv_path,
		source=source,
		dry_run=dry_run,
		log_path=str(base / "facturar_sin_factura_informe.json"),
		confirm=confirm,
	)
	from club_management.scripts.bulk_payments import run as run_apply

	informe_path = csv_path
	if source in ("inconsistencias", "apply_json") or "inconsistencias" in Path(csv_path).name:
		candidate = base / "Cobranza 01 a 28-08.xlsx"
		if candidate.is_file():
			informe_path = str(candidate)

	apply = run_apply(
		csv_path=informe_path,
		dry_run=dry_run,
		tolerance=tolerance,
		log_path=str(base / "apply_cobranzas_v9.json"),
		confirm=confirm,
	)
	return {"facturar": facturar, "apply": apply}
