"""Migración de inscripciones activas desde básquet legacy a actividad única Basquet."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe

from club_management.activities.services.actividades_icdpe_catalog import (
	_resolve_actividad_docname,
)
from club_management.activities.services.basquet_unified_map import (
	BASQUET_ACTIVIDAD,
	LEGACY_BASQUET_ACTIVIDADES,
	map_legacy_basquet_seleccion,
)
from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	_resolve_equipo_actividad,
	_resolve_grupo_actividad,
	sync_socio_actividad_resumen,
)


@dataclass
class MigrateBasquetStats:
	migradas: int = 0
	omitidas: int = 0
	huerfanas: int = 0
	errores: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"migradas": self.migradas,
			"omitidas": self.omitidas,
			"huerfanas": self.huerfanas,
			"errores": self.errores,
		}


def _titulo_actividad(actividad_name: str) -> str:
	return (frappe.db.get_value("Actividad", actividad_name, "titulo") or actividad_name or "").strip()


def _titulo_grupo(grupo_name: str | None) -> str:
	if not grupo_name:
		return ""
	return (frappe.db.get_value("Grupo Actividad", grupo_name, "titulo") or "").strip()


def _titulo_equipo(equipo_name: str | None) -> str:
	if not equipo_name:
		return ""
	return (frappe.db.get_value("Equipo Actividad", equipo_name, "titulo") or "").strip()


def _resolve_unified_targets(seleccion: dict[str, str]) -> dict[str, str] | None:
	actividad_name = _resolve_actividad_docname(seleccion["actividad"])
	if not actividad_name:
		return None
	grupo_name = _resolve_grupo_actividad(actividad_name, seleccion.get("grupo"))
	if not grupo_name:
		return None
	equipo_name = None
	equipo_key = (seleccion.get("equipo") or "").strip()
	if equipo_key:
		equipo_name = _resolve_equipo_actividad(grupo_name, equipo_key)
		if not equipo_name:
			return None
	return {
		"actividad": actividad_name,
		"grupo_actividad": grupo_name,
		"equipo_actividad": equipo_name,
	}


def migrate_basquet_inscripciones_activas() -> dict[str, Any]:
	"""Reasigna inscripciones activas de actividades básquet legacy a Basquet unificado."""
	if not frappe.db.table_exists("Inscripcion Actividad"):
		return MigrateBasquetStats().to_dict()

	stats = MigrateBasquetStats()
	legacy_names = [
		name
		for titulo in LEGACY_BASQUET_ACTIVIDADES
		if (name := frappe.db.get_value("Actividad", {"titulo": titulo}, "name"))
	]
	if not legacy_names:
		return stats.to_dict()

	socios_afectados: set[str] = set()
	for row in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": "Activa", "actividad": ["in", legacy_names]},
		fields=["name", "socio", "actividad", "grupo_actividad", "equipo_actividad"],
	):
		act_titulo = _titulo_actividad(row.actividad)
		grupo_titulo = _titulo_grupo(row.grupo_actividad)
		equipo_titulo = _titulo_equipo(row.equipo_actividad)
		seleccion = map_legacy_basquet_seleccion(act_titulo, grupo_titulo, equipo_titulo)
		if not seleccion:
			stats.huerfanas += 1
			stats.errores.append(
				f"Inscripción {row.name}: sin mapeo ({act_titulo} / {grupo_titulo} / {equipo_titulo})"
			)
			continue

		targets = _resolve_unified_targets(seleccion)
		if not targets:
			stats.huerfanas += 1
			stats.errores.append(
				f"Inscripción {row.name}: destino no encontrado ({seleccion})"
			)
			continue

		if (
			row.actividad == targets["actividad"]
			and row.grupo_actividad == targets["grupo_actividad"]
			and row.equipo_actividad == targets["equipo_actividad"]
		):
			stats.omitidas += 1
			continue

		frappe.db.set_value(
			INSCRIPCION_DOCTYPE,
			row.name,
			{
				"actividad": targets["actividad"],
				"grupo_actividad": targets["grupo_actividad"],
				"equipo_actividad": targets["equipo_actividad"],
			},
			update_modified=True,
		)
		stats.migradas += 1
		socios_afectados.add(row.socio)

	for socio in socios_afectados:
		sync_socio_actividad_resumen(socio)

	return stats.to_dict()


def ensure_basquet_unificado_disponible() -> None:
	"""Verifica que exista la actividad Basquet unificada (post-seed)."""
	if not _resolve_actividad_docname(BASQUET_ACTIVIDAD):
		frappe.throw(f"Actividad {BASQUET_ACTIVIDAD!r} no encontrada; ejecute el seed primero.")
