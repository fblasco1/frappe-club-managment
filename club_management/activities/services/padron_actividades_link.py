"""Mapeo e importación de inscripciones desde CSV del padrón por actividad."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe import _

from club_management.activities.services.inscripcion_socio import inscribir_socio_selecciones
from club_management.activities.services.estructura_actividades_seed import (
	seed_estructura_actividades_completa,
)

SOCIO_DOCTYPE = "Socio"

_CONCEPTOS_FEDERATIVOS = frozenset(
	{
		"CUOTA FEDERATIVA DE VOLEY",
		"CUOTA FEDERATIVA BASQUET - MINIBASQUET",
	}
)

_JUBILADO_CENTRO = "CENTRO DE JUBILADOS"

_PRESETS: dict[str, dict[str, str]] = {
	"GIMNASIA ARTISTICA 2 VECES POR SEMANA": {
		"actividad": "Gimnasia Artistica",
		"grupo": "2 Clases por Semana",
	},
	"GIMNASIA ARTISTICA 1 CLASE POR SEMANA": {
		"actividad": "Gimnasia Artistica",
		"grupo": "1 Clase por Semana",
	},
	"BOXEO 1 VEZ POR SEMANA": {"actividad": "Boxeo", "grupo": "1 Clase por Semana"},
	"BOXEO 2 VECES POR SEMANA": {"actividad": "Boxeo", "grupo": "2 Clases por Semana"},
	"MINI PATIN": {"actividad": "Patin Artistico", "grupo": "Patin Mini"},
	"PATIN AVANZADO": {"actividad": "Patin Artistico", "grupo": "Patin Avanzado"},
	"INTERMEDIO": {"actividad": "Patin Artistico", "grupo": "Patin Intermedio"},
	"ADULTO": {"actividad": "Patin Artistico", "grupo": "Adulto"},
	"VOLEY": {"actividad": "Voley Femenino", "grupo": "Tira"},
	"VOLEY ESCUELITA": {
		"actividad": "Voley Femenino",
		"grupo": "Escuelita Minivoley",
		"equipo": "Escuelita Minivoley",
	},
	"LIGA TABI": {"actividad": "Futbol", "grupo": "TABI A"},
	"TABI": {"actividad": "Futbol", "grupo": "TABI A"},
	"FAFI": {"actividad": "Futbol", "grupo": "FAFI"},
	"TABI B": {"actividad": "Futbol", "grupo": "TABI B"},
	"BASQUET ESCUELITA": {"actividad": "Basquet Escuelita", "grupo": "Mixta"},
	"DANZA": {"actividad": "Danza"},
	"TAEKWONDO": {"actividad": "Taekwondo"},
	"SHUI LU": {"actividad": "Shui Lu"},
	"RITMOS LATINOS": {"actividad": "Ritmos Latinos"},
	"INICIACION DEPORTIVA": {"actividad": "Iniciacion Deportiva", "grupo": "1 Clase por Semana"},
	"FUNCIONAL 1 CLASE POR SEMANA": {
		"actividad": "Funcional",
		"grupo": "1 Clase por Semana",
	},
	"FUNCIONAL 2 CLASES POR SEMANA": {
		"actividad": "Funcional",
		"grupo": "2 Clases por Semana",
	},
	"GAP 2 CLASES POR SEMANA": {"actividad": "Funcional", "grupo": "GAP"},
	"CROSSFIT 2 CLASES POR SEMANA": {"actividad": "Crossfit"},
	"ARTISTICA": {
		"actividad": "Gimnasia Artistica",
		"grupo": "2 Clases por Semana",
	},
}

_PATIN_GRUPO_ALIASES = {
	"AVANZADO": "Patin Avanzado",
	"INTERMEDIO": "Patin Intermedio",
	"MINI": "Patin Mini",
	"ADULTO": "Adulto",
}


def _normalize_label(label: str) -> str:
	return re.sub(r"\s+", " ", (label or "").strip())


def _normalize_key(label: str) -> str:
	return _normalize_label(label).upper()


def es_concepto_federativo(label: str) -> bool:
	return _normalize_key(label) in _CONCEPTOS_FEDERATIVOS


def es_jubilado_centro(label: str) -> bool:
	return _normalize_key(label) == _JUBILADO_CENTRO


def parse_actividad_mapeada(label: str) -> dict[str, str]:
	"""Convierte una etiqueta del CSV en selección para `inscribir_socio_selecciones`."""
	key = _normalize_key(label)
	if key in _PRESETS:
		return dict(_PRESETS[key])

	parts = [_normalize_label(part) for part in label.split("|") if _normalize_label(part)]
	if not parts:
		frappe.throw(_("Etiqueta de actividad vacía"))

	if len(parts) >= 3:
		return {
			"actividad": _title_actividad(parts[0]),
			"grupo": _title_grupo(parts[1]),
			"equipo": parts[2].strip(),
		}

	if len(parts) == 2:
		left, right = parts[0].upper(), parts[1].upper()
		if left in {"PATIN ARTISTICO", "PATIN ARTÍSTICO"}:
			grupo = _PATIN_GRUPO_ALIASES.get(right, _title_grupo(parts[1]))
			return {"actividad": "Patin Artistico", "grupo": grupo}
		if left == "VOLEY":
			return {
				"actividad": "Voley Femenino",
				"grupo": "Tira",
				"equipo": _title_equipo(parts[1]),
			}
		return {
			"actividad": _title_actividad(parts[0]),
			"grupo": _title_grupo(parts[1]),
		}

	frappe.throw(_("Etiqueta de actividad no reconocida: {0}").format(label))


def _title_actividad(value: str) -> str:
	mapping = {
		"BASQUET MASCULINO": "Basquet Masculino",
		"BASQUET ESCUELITA": "Basquet Escuelita",
		"VOLEY": "Voley Femenino",
		"PATIN ARTISTICO": "Patin Artistico",
		"PATIN ARTÍSTICO": "Patin Artistico",
		"FUTBOL": "Futbol",
		"LIGA TABI": "Futbol",
	}
	upper = value.upper()
	if upper in mapping:
		return mapping[upper]
	return value.strip().title()


def _title_grupo(value: str) -> str:
	mapping = {
		"TIRA AZUL": "Tira Azul",
		"TIRA AMARILLA": "Tira Amarilla",
		"TIRA FLEX": "Tira Flex",
		"TABI A": "TABI A",
		"TABI B": "TABI B",
		"SUPERIOR A": "Superior A",
		"SUPERIOR B": "Superior B",
		"ESCUELITA MINIVOLEY": "Escuelita Minivoley",
	}
	upper = value.upper()
	if upper in mapping:
		return mapping[upper]
	if upper in _PATIN_GRUPO_ALIASES:
		return _PATIN_GRUPO_ALIASES[upper]
	return value.strip().title()


def _title_equipo(value: str) -> str:
	upper = value.upper()
	if upper.startswith("U") and upper[1:].isdigit():
		return upper
	return value.strip()


def find_socio_by_nro_padron(nro_socio: str) -> str | None:
	key = (nro_socio or "").strip()
	if not key:
		return None
	meta = frappe.get_meta(SOCIO_DOCTYPE)
	if meta.has_field("nro_socio_padron"):
		name = frappe.db.get_value(SOCIO_DOCTYPE, {"nro_socio_padron": key}, "name")
		if name:
			return name
	return frappe.db.get_value(SOCIO_DOCTYPE, {"name": key}, "name")


def _parse_csv_rows(csv_path: Path) -> list[dict[str, str]]:
	with csv_path.open(encoding="utf-8-sig", newline="") as handle:
		return list(csv.DictReader(handle))


def _split_actividades(raw: str) -> list[str]:
	if not raw:
		return []
	# Preferir `;;` entre actividades distintas (compuestas usan ` | ` internamente).
	if ";;" in raw:
		parts = raw.split(";;")
	else:
		parts = [raw]
	return [_normalize_label(part) for part in parts if _normalize_label(part)]


def _marcar_jubilado(socio_name: str, *, dry_run: bool) -> None:
	categoria = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "categoria")
	if categoria == "Jubilado":
		return
	if dry_run:
		return
	frappe.db.set_value(SOCIO_DOCTYPE, socio_name, "categoria", "Jubilado", update_modified=True)


@dataclass
class PadronActividadesStats:
	total_filas: int = 0
	socios_procesados: int = 0
	inscripciones_creadas: int = 0
	inscripciones_existentes: int = 0
	jubilados_marcados: int = 0
	federativas_omitidas: int = 0
	socios_no_encontrados: int = 0
	sin_actividades: int = 0
	errores: list[str] = field(default_factory=list)

	def to_dict(self) -> dict[str, Any]:
		return {
			"total_filas": self.total_filas,
			"socios_procesados": self.socios_procesados,
			"inscripciones_creadas": self.inscripciones_creadas,
			"inscripciones_existentes": self.inscripciones_existentes,
			"jubilados_marcados": self.jubilados_marcados,
			"federativas_omitidas": self.federativas_omitidas,
			"socios_no_encontrados": self.socios_no_encontrados,
			"sin_actividades": self.sin_actividades,
			"errores": self.errores,
		}


def importar_socios_actividades_padron(
	*,
	csv_path: str,
	dry_run: bool = True,
	ensure_seed: bool = True,
) -> dict[str, Any]:
	path = Path(csv_path)
	if not path.is_file():
		frappe.throw(_("CSV no encontrado: {0}").format(csv_path))

	if ensure_seed and not dry_run:
		seed_estructura_actividades_completa(crear_equipos=True)

	rows = _parse_csv_rows(path)
	stats = PadronActividadesStats(total_filas=len(rows))

	for row in rows:
		nro_socio = (row.get("nro_socio") or "").strip()
		nombre = (row.get("nombre") or "").strip()
		labels = _split_actividades(row.get("actividades_mapeadas") or "")

		if not nro_socio:
			continue

		socio_name = find_socio_by_nro_padron(nro_socio)
		if not socio_name:
			stats.socios_no_encontrados += 1
			stats.errores.append(
				_("Socio no encontrado nro {0} ({1})").format(nro_socio, nombre or "—")
			)
			continue

		stats.socios_procesados += 1
		if not labels:
			stats.sin_actividades += 1
			continue

		selecciones: list[dict[str, str]] = []
		jubilado = False
		for label in labels:
			if es_jubilado_centro(label):
				jubilado = True
				continue
			if es_concepto_federativo(label):
				stats.federativas_omitidas += 1
				continue
			try:
				selecciones.append(parse_actividad_mapeada(label))
			except Exception as exc:  # noqa: BLE001 — lote continúa
				stats.errores.append(
					_("Nro {0} etiqueta «{1}»: {2}").format(nro_socio, label, str(exc)[:160])
				)

		if jubilado:
			stats.jubilados_marcados += 1
			_marcar_jubilado(socio_name, dry_run=dry_run)

		if not selecciones:
			continue

		if dry_run:
			stats.inscripciones_creadas += len(selecciones)
			continue

		activas_antes = frappe.db.count(
			"Inscripcion Actividad",
			{"socio": socio_name, "estado": "Activa"},
		)
		try:
			inscribir_socio_selecciones(socio_name, selecciones, activar=False)
		except Exception as exc:  # noqa: BLE001
			stats.errores.append(
				_("Nro {0} inscripción: {1}").format(nro_socio, str(exc)[:200])
			)
			continue
		activas_despues = frappe.db.count(
			"Inscripcion Actividad",
			{"socio": socio_name, "estado": "Activa"},
		)
		nuevas = max(0, activas_despues - activas_antes)
		stats.inscripciones_creadas += nuevas
		stats.inscripciones_existentes += len(selecciones) - nuevas

	if not dry_run:
		frappe.db.commit()

	return stats.to_dict()


def default_padron_csv_path() -> str:
	candidates = [
		Path("/mnt/c/Users/USUARIO/Desktop/socios_actividades_mapeadas.csv"),
		Path(frappe.get_site_path("private/files/socios_actividades_mapeadas.csv")),
	]
	for candidate in candidates:
		if candidate.is_file():
			return str(candidate)
	return str(candidates[0])
