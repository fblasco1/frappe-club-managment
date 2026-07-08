"""Mapeo básquet legacy → actividad única Basquet (spec basquet_estructura_unificada.md)."""

from __future__ import annotations

BASQUET_ACTIVIDAD = "Basquet"

LEGACY_BASQUET_ACTIVIDADES: frozenset[str] = frozenset(
	{
		"Basquet Masculino",
		"Basquet Femenino",
		"Basquet Escuelita",
	}
)

_ALL_BASQUET_ACTIVIDADES: frozenset[str] = LEGACY_BASQUET_ACTIVIDADES | {BASQUET_ACTIVIDAD}

_GRUPO_LEGACY_MASCULINO: dict[str, str] = {
	"Tira Azul": "Masculino / Azul",
	"Tira Amarilla": "Masculino / Amarillo",
	"Tira Flex": "Masculino / Flex",
}


def normalize_escuelita_equipo(equipo_titulo: str) -> str:
	"""Normaliza títulos de equipo escuelita (legacy vs seed unificado)."""
	key = (equipo_titulo or "").strip().upper().replace(" ", "")
	if key in {"U7/U9", "U7U9"}:
		return "U7 / U9"
	if key in {"U11/U13", "U11U13"}:
		return "U11 / U13"
	return (equipo_titulo or "").strip()


def map_legacy_basquet_grupo(
	actividad_titulo: str,
	grupo_titulo: str,
	*,
	equipo_titulo: str = "",
) -> str | None:
	"""Devuelve el título de grupo unificado o None si no aplica."""
	act = (actividad_titulo or "").strip()
	grupo = (grupo_titulo or "").strip()
	equipo = (equipo_titulo or "").strip()
	if act == "Basquet Masculino":
		return _GRUPO_LEGACY_MASCULINO.get(grupo)
	if act == "Basquet Escuelita" and grupo == "Mixta":
		return "Mixto / Escuela"
	if act == "Basquet Femenino" and grupo == "Femenino":
		if equipo == "Superior Fem":
			return "Femenino / Superior"
		return "Femenino / Formativa"
	return None


def map_legacy_basquet_seleccion(
	actividad: str,
	grupo: str,
	equipo: str = "",
) -> dict[str, str] | None:
	"""Convierte selección legacy a actividad Basquet unificada."""
	act = (actividad or "").strip()
	if act not in LEGACY_BASQUET_ACTIVIDADES:
		return None
	new_grupo = map_legacy_basquet_grupo(act, grupo, equipo_titulo=equipo)
	if not new_grupo:
		return None
	new_equipo = (equipo or "").strip()
	if act == "Basquet Escuelita":
		new_equipo = normalize_escuelita_equipo(new_equipo)
	return {
		"actividad": BASQUET_ACTIVIDAD,
		"grupo": new_grupo,
		"equipo": new_equipo,
	}


def normalize_basquet_seleccion(
	actividad: str,
	grupo: str,
	equipo: str = "",
) -> dict[str, str]:
	"""Devuelve selección unificada; pasa through si ya es Basquet u otro deporte."""
	mapped = map_legacy_basquet_seleccion(actividad, grupo, equipo)
	if mapped:
		return mapped
	return {
		"actividad": (actividad or "").strip(),
		"grupo": (grupo or "").strip(),
		"equipo": (equipo or "").strip(),
	}


def map_roster_basquet_seleccion(categoria: str, equipo: str) -> dict[str, str]:
	"""Mapea categoría/equipo del roster Excel a selección unificada."""
	cat = (categoria or "").strip().upper()
	eq = (equipo or "").strip().title()
	if eq == "Mayor":
		eq = "MAYOR"

	if eq == "Femenino":
		if cat in {"MAYOR", "U21"}:
			return {
				"actividad": BASQUET_ACTIVIDAD,
				"grupo": "Femenino / Superior",
				"equipo": "Superior Fem",
			}
		equipo_titulo = "U9" if cat == "U7" else cat
		return {
			"actividad": BASQUET_ACTIVIDAD,
			"grupo": "Femenino / Formativa",
			"equipo": equipo_titulo,
		}

	if eq == "Escuelita" or (cat in {"U7", "U9"} and eq not in {"Azul", "Amarillo", "Flex", "MAYOR"}):
		equipo_titulo = "U7 / U9" if cat in {"U7", "U9"} else "U11 / U13"
		return {
			"actividad": BASQUET_ACTIVIDAD,
			"grupo": "Mixto / Escuela",
			"equipo": equipo_titulo,
		}

	if eq in {"Azul", "Amarillo"}:
		equipo_titulo = "U21" if cat in {"MAYOR", "U21"} else cat
		return {
			"actividad": BASQUET_ACTIVIDAD,
			"grupo": f"Masculino / {eq}",
			"equipo": equipo_titulo,
		}

	if eq == "Flex":
		if cat == "MAYOR":
			equipo_titulo = "Superior C"
		elif cat in {"U17", "U21"}:
			equipo_titulo = "U19"
		else:
			equipo_titulo = "U15"
		return {
			"actividad": BASQUET_ACTIVIDAD,
			"grupo": "Masculino / Flex",
			"equipo": equipo_titulo,
		}

	if eq == "MAYOR" and cat == "MAYOR":
		return {
			"actividad": BASQUET_ACTIVIDAD,
			"grupo": "Masculino / Flex",
			"equipo": "Superior C",
		}

	raise ValueError(f"Equipo de básquet no reconocido para {cat} / {equipo}")


def map_padron_basquet_grupo(actividad_titulo: str, grupo_titulo: str) -> str:
	"""Mapea grupo del padrón (legacy o unificado) al título unificado."""
	act = (actividad_titulo or "").strip()
	grupo = (grupo_titulo or "").strip()
	mapped = map_legacy_basquet_grupo(act, grupo)
	if mapped:
		return mapped
	upper = grupo.upper()
	if upper == "TIRA AZUL":
		return "Masculino / Azul"
	if upper == "TIRA AMARILLA":
		return "Masculino / Amarillo"
	if upper == "TIRA FLEX":
		return "Masculino / Flex"
	if upper == "MIXTA":
		return "Mixto / Escuela"
	if upper == "FEMENINO" and act in LEGACY_BASQUET_ACTIVIDADES | {BASQUET_ACTIVIDAD}:
		return "Femenino / Formativa"
	return grupo


def basquet_actividad_docnames() -> list[str]:
	"""Nombres de DocType Actividad relacionados con básquet (legacy + unificado)."""
	import frappe

	names: list[str] = []
	for titulo in _ALL_BASQUET_ACTIVIDADES:
		name = frappe.db.get_value("Actividad", {"titulo": titulo}, "name")
		if name:
			names.append(name)
	return names
