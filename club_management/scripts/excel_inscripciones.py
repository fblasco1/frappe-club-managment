"""Mapeo del Excel «Socios SIN ACTIVIDAD ASIGNADA» a inscripciones."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from club_management.activities.services.basquet_unified_map import (
	BASQUET_ACTIVIDAD,
	normalize_escuelita_equipo,
)
from club_management.scripts.bulk_io import parse_fecha

_SKIP_ACTIVIDAD = frozenset(
	{
		"ADHERENTE",
		"BECADO",
		"SIN ACTIVIDAD",
		"CENTRO JUBILADO",
		"JUBILADO",
		"",
	}
)


def _norm(value: Any) -> str:
	return re.sub(r"\s+", " ", str(value or "")).strip()


def map_seleccion_excel(
	actividad: str,
	grupo: str = "",
	equipo: str = "",
) -> tuple[list[dict[str, str]], str | None]:
	"""Devuelve selecciones `{actividad, grupo, equipo}` o código de omisión/error."""
	act = _norm(actividad).upper()
	grp = _norm(grupo).upper()
	eq = _norm(equipo).upper()

	if act in _SKIP_ACTIVIDAD:
		return [], "omitido_sin_deporte"

	if act in {"BASQUET", "BASQUET ESCUELA"} or act.startswith("BASQUET"):
		return _map_basquet(grp, eq)

	if act == "VOLEY":
		if grp in {"ESCUELA", "ESCUELITA"}:
			return (
				[{"actividad": "Voley Femenino", "grupo": "Escuelita Minivoley", "equipo": "Escuelita Minivoley"}],
				None,
			)
		if grp == "TIRA":
			return ([{"actividad": "Voley Femenino", "grupo": "Tira", "equipo": eq.title() if eq else ""}], None)
		return ([{"actividad": "Voley Femenino", "grupo": "Tira", "equipo": ""}], None)

	if act == "FUTBOL":
		if grp in {"ESCUELITA", "ESCUELA"}:
			return ([{"actividad": "Futbol", "grupo": "TABI A", "equipo": ""}], "grupo_aproximado")
		if "TABI" in grp:
			return ([{"actividad": "Futbol", "grupo": "TABI A" if "B" not in grp else "TABI B", "equipo": ""}], None)
		if "FAFI" in grp:
			return ([{"actividad": "Futbol", "grupo": "FAFI", "equipo": ""}], None)
		return ([{"actividad": "Futbol", "grupo": grp.title(), "equipo": ""}], None)

	if act == "TAEKWONDO":
		return ([{"actividad": "Taekwondo", "grupo": "", "equipo": ""}], None)

	if act == "GIMNASIA ARTISTICA":
		return (
			[{"actividad": "Gimnasia Artistica", "grupo": "1 Clase por Semana", "equipo": ""}],
			"grupo_aproximado",
		)

	if act in {"GIMNASIA ARTISTICA/DANZA", "GIMNASIA ARTISTICA / DANZA"}:
		return (
			[
				{"actividad": "Gimnasia Artistica", "grupo": "1 Clase por Semana", "equipo": ""},
				{"actividad": "Danza", "grupo": "", "equipo": ""},
			],
			"grupo_aproximado",
		)

	if act == "PATIN":
		grupo_patin = {
			"INICIAL": "Patin Mini",
			"MINI": "Patin Mini",
			"INTERMEDIO": "Patin Intermedio",
			"AVANZADO": "Patin Avanzado",
			"ADULTO": "Adulto",
		}.get(grp, grp.title())
		return ([{"actividad": "Patin Artistico", "grupo": grupo_patin, "equipo": ""}], None)

	if act == "FUNCIONAL":
		if grp == "GAP":
			return (
				[{"actividad": "Funcional", "grupo": "GAP 1 vez/sem - Prof Noelia", "equipo": ""}],
				"grupo_aproximado",
			)
		return ([{"actividad": "Funcional", "grupo": "", "equipo": ""}], None)

	if act == "DANZA":
		return ([{"actividad": "Danza", "grupo": "", "equipo": ""}], None)

	return ([{"actividad": actividad.strip().title(), "grupo": grupo.strip(), "equipo": equipo.strip()}], None)


def _map_basquet(grp: str, eq: str) -> tuple[list[dict[str, str]], str | None]:
	if grp in {"ESCUELA", "ESCUELITA"}:
		if eq in {"U7", "U9"}:
			equipo = "U7 / U9"
		elif eq in {"U11", "U13"}:
			equipo = "U11 / U13"
		else:
			equipo = normalize_escuelita_equipo(eq)
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Mixto / Escuela", "equipo": equipo}], None)
	if grp in {"AMARILLO", "AMARILLA"}:
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Masculino / Amarillo", "equipo": eq or ""}], None)
	if grp == "AZUL":
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Masculino / Azul", "equipo": eq or ""}], None)
	if grp == "FLEX":
		flex_eq = eq
		if eq == "SUPERIOR":
			flex_eq = "Superior C"
		elif eq in {"U17", "U21"}:
			flex_eq = "U19"
		elif eq in {"U13", "U15"}:
			flex_eq = "U15"
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Masculino / Flex", "equipo": flex_eq}], None)
	if grp == "FEMENINO":
		if eq == "SUPERIOR":
			return (
				[{"actividad": BASQUET_ACTIVIDAD, "grupo": "Femenino / Superior", "equipo": "Superior Fem"}],
				None,
			)
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Femenino / Formativa", "equipo": eq or ""}], None)
	if eq.startswith("U"):
		if eq in {"U7", "U9"}:
			equipo = "U7 / U9"
		elif eq in {"U11", "U13"}:
			equipo = "U11 / U13"
		else:
			equipo = eq
		return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": "Mixto / Escuela", "equipo": equipo}], None)
	return ([{"actividad": BASQUET_ACTIVIDAD, "grupo": grp.title(), "equipo": eq}], None)


def filas_from_socios_excel(rows: list[tuple[Any, ...]]) -> list[dict[str, str]]:
	"""Convierte filas del Excel Desk-export a filas de inscripción (puede expandir 1→N)."""
	if not rows:
		return []
	header = [_norm(h) for h in rows[0]]
	idx = {h.lower(): i for i, h in enumerate(header)}

	def col(*names: str) -> int | None:
		for name in names:
			if name.lower() in idx:
				return idx[name.lower()]
		return None

	i_nro = col("Número de Socio", "Numero de Socio", "nro_socio")
	i_dni = col("DNI")
	i_act = col("Actividad")
	i_grp = col("Grupo")
	i_eq = col("Equipo")
	i_fecha = col("Fecha de ingreso", "fecha_desde")
	out: list[dict[str, str]] = []
	for raw in rows[1:]:
		vals = list(raw)
		if i_nro is None or i_nro >= len(vals) or vals[i_nro] is None:
			continue
		nro = vals[i_nro]
		nro_s = str(int(nro)) if isinstance(nro, float) else str(nro).strip()
		dni = str(vals[i_dni]).strip() if i_dni is not None and i_dni < len(vals) and vals[i_dni] else ""
		act = str(vals[i_act]).strip() if i_act is not None and i_act < len(vals) and vals[i_act] else ""
		grp = str(vals[i_grp]).strip() if i_grp is not None and i_grp < len(vals) and vals[i_grp] else ""
		eq = str(vals[i_eq]).strip() if i_eq is not None and i_eq < len(vals) and vals[i_eq] else ""
		fecha_raw = vals[i_fecha] if i_fecha is not None and i_fecha < len(vals) else None
		fecha = ""
		if isinstance(fecha_raw, datetime):
			fecha = fecha_raw.date().isoformat()
		elif isinstance(fecha_raw, date):
			fecha = fecha_raw.isoformat()
		elif fecha_raw:
			parsed = parse_fecha(str(fecha_raw))
			fecha = parsed.isoformat() if parsed else ""
		selecciones, skip = map_seleccion_excel(act, grp, eq)
		if skip == "omitido_sin_deporte" or not selecciones:
			out.append(
				{
					"nro_socio": nro_s,
					"dni": dni,
					"actividad": "",
					"grupo_actividad": "",
					"equipo_actividad": "",
					"fecha_desde": fecha,
					"skip_reason": "omitido_sin_deporte",
					"actividad_origen": act,
				}
			)
			continue
		for sel in selecciones:
			out.append(
				{
					"nro_socio": nro_s,
					"dni": dni,
					"actividad": sel.get("actividad") or "",
					"grupo_actividad": sel.get("grupo") or "",
					"equipo_actividad": sel.get("equipo") or "",
					"fecha_desde": fecha,
					"skip_reason": skip or "",
					"actividad_origen": act,
				}
			)
	return out
