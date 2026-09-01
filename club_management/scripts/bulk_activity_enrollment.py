"""Vinculación masiva de socios a actividades (`Inscripcion Actividad`).

Spec: `club_management/specs/vinculacion_masiva_actividades.md`

    bench --site dev.localhost execute club_management.scripts.bulk_activity_enrollment.run \\
        --kwargs '{"csv_path": "/ruta/inscripciones.csv", "dry_run": true}'
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, today

from club_management.activities.services.actividades_catalog import ensure_actividad_exists
from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	_resolve_equipo_actividad,
	_resolve_grupo_actividad,
	inscribir_socio_selecciones,
	sync_socio_actividad_resumen,
)
from club_management.scripts.bulk_io import cell, ensure_not_production, find_socio, parse_fecha, read_bulk_rows

SOCIO_DOCTYPE = "Socio"


@dataclass
class BulkEnrollmentStats:
	total_filas: int = 0
	altas: int = 0
	simuladas: int = 0
	ya_inscrito: int = 0
	omitidos: int = 0
	inscripciones: list[str] = field(default_factory=list)
	errores: list[dict[str, Any]] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"altas": self.altas,
			"simuladas": self.simuladas,
			"ya_inscrito": self.ya_inscrito,
			"omitidos": self.omitidos,
			"inscripciones": self.inscripciones,
			"errores": self.errores,
		}


def resolve_jerarquia(
	actividad_key: str,
	grupo_key: str,
	equipo_key: str,
) -> tuple[str | None, str | None, str | None, str | None]:
	"""Devuelve (actividad, grupo, equipo, codigo_error)."""
	actividad_name = ensure_actividad_exists(actividad_key)
	if not actividad_name:
		return None, None, None, "actividad_no_encontrada"

	usa_grupos = bool(frappe.db.get_value("Actividad", actividad_name, "usa_grupos"))
	grupo_name = None
	if usa_grupos:
		if not grupo_key:
			return actividad_name, None, None, "grupo_no_encontrado"
		grupo_name = _resolve_grupo_actividad(actividad_name, grupo_key)
		if not grupo_name:
			return actividad_name, None, None, "grupo_no_encontrado"
	elif grupo_key:
		return actividad_name, None, None, "grupo_no_encontrado"

	equipo_name = None
	if equipo_key:
		if not grupo_name:
			return actividad_name, grupo_name, None, "equipo_no_encontrado"
		equipo_name = _resolve_equipo_actividad(grupo_name, equipo_key)
		if not equipo_name:
			return actividad_name, grupo_name, None, "equipo_no_encontrado"

	return actividad_name, grupo_name, equipo_name, None


def inscripcion_activa_existe(
	socio_name: str,
	actividad: str,
	grupo: str | None,
	equipo: str | None,
) -> bool:
	filters: dict[str, Any] = {
		"socio": socio_name,
		"estado": "Activa",
		"actividad": actividad,
	}
	if grupo:
		filters["grupo_actividad"] = grupo
		if equipo:
			filters["equipo_actividad"] = equipo
	else:
		filters["grupo_actividad"] = ["is", "not set"]
	return bool(frappe.db.exists(INSCRIPCION_DOCTYPE, filters))


def _add_error(stats: BulkEnrollmentStats, fila: int, codigo: str, **extra: Any) -> None:
	stats.errores.append({"fila": fila, "codigo": codigo, **extra})


def _write_log(stats: BulkEnrollmentStats, log_path: str | None) -> str | None:
	if not log_path:
		return None
	path = Path(log_path)
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
	return str(path)


def _print_resumen(stats: BulkEnrollmentStats, *, dry_run: bool, csv_path: str) -> None:
	mode = "SIMULACIÓN (dry_run)" if dry_run else "INSCRIPCIONES EJECUTADAS"
	print("\n" + "=" * 72)
	print(f" VINCULACIÓN MASIVA ACTIVIDADES — {mode}")
	print("=" * 72)
	print(f" CSV                             : {csv_path}")
	data = stats.to_dict()
	for key, value in data.items():
		if key in {"errores", "inscripciones"}:
			continue
		print(f" {key:30s}: {value}")
	if stats.errores:
		print("-" * 72)
		print(" Errores (primeros 25):")
		for err in stats.errores[:25]:
			print(f"   - {err}")
		remaining = len(stats.errores) - 25
		if remaining > 0:
			print(f"   ... y {remaining} más")
	print("=" * 72 + "\n")


def run(
	*,
	csv_path: str,
	dry_run: bool = True,
	limit: int | None = None,
	log_path: str | None = None,
	commit_every: int = 25,
	confirm: str = "",
) -> dict[str, Any]:
	"""Procesa el CSV/Excel de inscripciones. Default: dry-run."""
	ensure_not_production(dry_run=dry_run, confirm=confirm)
	rows = read_bulk_rows(csv_path)
	stats = BulkEnrollmentStats(total_filas=len(rows))
	applied = 0

	for idx, raw in enumerate(rows, start=2):
		if limit is not None and (stats.altas + stats.simuladas + stats.ya_inscrito) >= limit:
			break
		nro = cell(raw, "nro_socio", "numero_socio", "nro")
		dni = cell(raw, "dni")
		actividad_key = cell(raw, "actividad")
		grupo_key = cell(raw, "grupo_actividad", "grupo")
		equipo_key = cell(raw, "equipo_actividad", "equipo")
		fecha_raw = cell(raw, "fecha_desde", "fecha_inscripcion", "fecha")
		skip_reason = cell(raw, "skip_reason")

		if skip_reason == "omitido_sin_deporte":
			stats.omitidos += 1
			continue

		socio_name = find_socio(nro_socio=nro, dni=dni)
		if not socio_name:
			_add_error(stats, idx, "socio_no_encontrado", nro_socio=nro, dni=dni)
			continue

		estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
		if estado != "Activo":
			_add_error(stats, idx, "socio_no_activo", socio=socio_name, estado=estado)
			continue

		if not actividad_key:
			_add_error(stats, idx, "actividad_no_encontrada", socio=socio_name)
			continue

		actividad, grupo, equipo, err = resolve_jerarquia(actividad_key, grupo_key, equipo_key)
		if err:
			_add_error(
				stats,
				idx,
				err,
				socio=socio_name,
				actividad=actividad_key,
				grupo=grupo_key,
				equipo=equipo_key,
			)
			continue

		fecha = parse_fecha(fecha_raw) if fecha_raw else getdate(today())
		if fecha_raw and not fecha:
			_add_error(stats, idx, "fecha_invalida", socio=socio_name, fecha_desde=fecha_raw)
			continue

		assert actividad is not None
		if inscripcion_activa_existe(socio_name, actividad, grupo, equipo):
			stats.ya_inscrito += 1
			continue

		if dry_run:
			stats.simuladas += 1
			continue

		antes = frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"socio": socio_name, "estado": "Activa"},
			pluck="name",
		)
		inscribir_socio_selecciones(
			socio_name,
			[{"actividad": actividad, "grupo": grupo, "equipo": equipo}],
			activar=False,
			fecha_inscripcion=str(fecha) if fecha else None,
		)
		sync_socio_actividad_resumen(socio_name)
		despues = frappe.get_all(
			INSCRIPCION_DOCTYPE,
			filters={"socio": socio_name, "estado": "Activa"},
			pluck="name",
		)
		nuevas = [name for name in despues if name not in set(antes)]
		stats.altas += 1
		stats.inscripciones.extend(nuevas)
		applied += 1
		if commit_every and applied % commit_every == 0 and not getattr(frappe.flags, "in_test", False):
			frappe.db.commit()

	if not dry_run and applied and not getattr(frappe.flags, "in_test", False):
		frappe.db.commit()

	log = _write_log(stats, log_path)
	payload = stats.to_dict()
	payload["dry_run"] = dry_run
	payload["log_path"] = log
	_print_resumen(stats, dry_run=dry_run, csv_path=csv_path)
	return payload
