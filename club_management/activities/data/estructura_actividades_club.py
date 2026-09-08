"""Estructura operativa de actividades, grupos/tiras y equipos del club ICDPE.

Secretaría puede ajustar nombres e ítems en Desk; este módulo es la fuente para el patch de seed.
"""

from __future__ import annotations

from dataclasses import dataclass

from club_management.activities.data.basquet_aranceles_icdpe import (
	ITEM_ESCUELITA,
	ITEM_FEMENINO_SUP,
	ITEM_FORMATIVAS_AMARILLA,
	ITEM_FORMATIVAS_AZUL,
	ITEM_FORMATIVAS_FLEX,
	ITEM_MINIBASQUET,
)
from club_management.activities.data.futbol_aranceles_icdpe import (
	GRUPO_FUTBOL_ESCUELITA,
	ITEM_FUTBOL_FAFI,
	ITEM_FUTBOL_TABI_A,
	ITEM_FUTBOL_TABI_B,
)
from club_management.activities.data.otras_actividades_aranceles_icdpe import (
	ITEM_BOXEO_1_CLASE,
	ITEM_BOXEO_2_CLASES,
	ITEM_BOXEO_3_CLASES,
	ITEM_FUNCIONAL_1_CLASE,
	ITEM_FUNCIONAL_2_CLASES,
	ITEM_GIMNASIA_1_CLASE,
	ITEM_GIMNASIA_2_CLASES,
	ITEM_GYM_NO_SOCIO,
	ITEM_GYM_SOCIO,
	ITEM_INICIACION_1_CLASE,
	ITEM_INICIACION_2_CLASES,
	ITEM_YOGA_1_CLASE,
	ITEM_YOGA_2_CLASES,
)
from club_management.activities.data.patin_aranceles_icdpe import (
	ITEM_PATIN_AVANZADO,
	ITEM_PATIN_DANZA,
	ITEM_PATIN_INTERMEDIO,
	ITEM_PATIN_MINI,
	ITEM_PATIN_ADULTO,
	ITEM_PATIN_TEENS,
)
from club_management.activities.data.voley_aranceles_icdpe import (
	ITEM_VOLEY_ESCUELA,
	ITEM_VOLEY_FEDERADO,
)

# Categorías genéricas para deportes sin matriz ICDPE detallada (vóley, fútbol).
CATEGORIAS_EQUIPO: tuple[str, ...] = (
	"Categoria U7",
	"Categoria U9",
	"Categoria U11",
	"Categoria U13",
	"Categoria U15",
	"Categoria U17",
	"Primera",
)


@dataclass(frozen=True)
class EquipoSeed:
	titulo: str
	orden: int
	item_code: str
	descripcion: str = ""


@dataclass(frozen=True)
class GrupoSeed:
	titulo: str
	orden: int
	item_code: str | None = None
	"""Arancel único del grupo si todos los equipos comparten ítem."""
	equipos: tuple[EquipoSeed, ...] = ()
	"""Equipos con ítem propio (básquet ICDPE). Vacío → seed genérico `CATEGORIAS_EQUIPO`."""


@dataclass(frozen=True)
class ActividadEstructuraSeed:
	actividad: str
	grupos: tuple[GrupoSeed, ...]


def _eq(titulo: str, orden: int, item_code: str, descripcion: str = "") -> EquipoSeed:
	return EquipoSeed(titulo, orden, item_code, descripcion)


def _eq_basquet(titulo: str, orden: int, item_code: str, descripcion: str = "") -> EquipoSeed:
	return _eq(titulo, orden, item_code, descripcion)


def _grupo_leaf(grupo_titulo: str, orden: int, item_code: str) -> GrupoSeed:
	return GrupoSeed(
		grupo_titulo,
		orden,
		item_code=item_code,
		equipos=(_eq(grupo_titulo, 10, item_code),),
	)


ESTRUCTURA_BASQUET = ActividadEstructuraSeed(
	"Basquet",
	(
		GrupoSeed(
			"Masculino / Azul",
			10,
			equipos=(
				_eq_basquet("U9", 10, ITEM_MINIBASQUET, "PRE MINI"),
				_eq_basquet("U11", 20, ITEM_MINIBASQUET, "MINI"),
				_eq_basquet("U13", 30, ITEM_MINIBASQUET, "INFANTIL"),
				_eq_basquet("U15", 40, ITEM_FORMATIVAS_AZUL, "CADETE"),
				_eq_basquet("U17", 50, ITEM_FORMATIVAS_AZUL, "JUVENIL"),
				_eq_basquet("U21", 60, ITEM_FORMATIVAS_AZUL, "LIGA PROXIMO"),
			),
		),
		GrupoSeed(
			"Masculino / Amarillo",
			20,
			equipos=(
				_eq_basquet("U9", 10, ITEM_MINIBASQUET, "PRE MINI"),
				_eq_basquet("U11", 20, ITEM_MINIBASQUET, "MINI"),
				_eq_basquet("U13", 30, ITEM_MINIBASQUET, "INFANTIL"),
				_eq_basquet("U15", 40, ITEM_FORMATIVAS_AMARILLA, "CADETE"),
				_eq_basquet("U17", 50, ITEM_FORMATIVAS_AMARILLA, "JUVENIL"),
				_eq_basquet("U21", 60, ITEM_FORMATIVAS_AMARILLA, "LIGA PROXIMO"),
			),
		),
		GrupoSeed(
			"Masculino / Flex",
			30,
			equipos=(
				_eq_basquet("U15", 10, ITEM_FORMATIVAS_FLEX, "CADETE"),
				_eq_basquet("U19", 20, ITEM_FORMATIVAS_FLEX, "JUVENIL"),
				_eq_basquet("Superior C", 30, ITEM_FORMATIVAS_FLEX, 'SUPERIOR "C"'),
			),
		),
		GrupoSeed(
			"Femenino / Formativa",
			40,
			equipos=(
				_eq_basquet("U9", 10, ITEM_ESCUELITA),
				_eq_basquet("U11", 20, ITEM_ESCUELITA),
				_eq_basquet("U13", 30, ITEM_ESCUELITA),
				_eq_basquet("U15", 40, ITEM_ESCUELITA),
				_eq_basquet("U17", 50, ITEM_ESCUELITA),
			),
		),
		GrupoSeed(
			"Femenino / Superior",
			50,
			equipos=(_eq_basquet("Superior Fem", 10, ITEM_FEMENINO_SUP),),
		),
		GrupoSeed(
			"Mixto / Escuela",
			60,
			equipos=(
				_eq_basquet("U7 / U9", 10, ITEM_ESCUELITA),
				_eq_basquet("U11 / U13", 20, ITEM_ESCUELITA),
			),
		),
	),
)


ESTRUCTURA_VOLEY_FEMENINO = ActividadEstructuraSeed(
	"Voley Femenino",
	(
		GrupoSeed(
			"Tira",
			10,
			item_code=ITEM_VOLEY_FEDERADO,
			equipos=(
				_eq("U11", 10, ITEM_VOLEY_FEDERADO),
				_eq("U12", 20, ITEM_VOLEY_FEDERADO),
				_eq("U13", 30, ITEM_VOLEY_FEDERADO),
				_eq("U14", 40, ITEM_VOLEY_FEDERADO),
				_eq("U15", 50, ITEM_VOLEY_FEDERADO),
				_eq("U16", 60, ITEM_VOLEY_FEDERADO),
				_eq("U18", 70, ITEM_VOLEY_FEDERADO),
				_eq("U21", 80, ITEM_VOLEY_FEDERADO),
				_eq("Superior A", 90, ITEM_VOLEY_FEDERADO, 'SUPERIOR "A"'),
				_eq("Superior B", 100, ITEM_VOLEY_FEDERADO, 'SUPERIOR "B"'),
			),
		),
		GrupoSeed(
			"Escuela Adolescente",
			20,
			item_code=ITEM_VOLEY_ESCUELA,
			equipos=(_eq("Escuela Adolescente", 10, ITEM_VOLEY_ESCUELA),),
		),
		GrupoSeed(
			"Escuelita Minivoley",
			30,
			item_code=ITEM_VOLEY_ESCUELA,
			equipos=(_eq("Escuelita Minivoley", 10, ITEM_VOLEY_ESCUELA),),
		),
	),
)

ESTRUCTURA_FUTBOL = ActividadEstructuraSeed(
	"Futbol",
	(
		GrupoSeed(
			"FAFI",
			10,
			item_code=ITEM_FUTBOL_FAFI,
			equipos=(
				_eq("2019", 10, ITEM_FUTBOL_FAFI),
				_eq("2018", 20, ITEM_FUTBOL_FAFI),
				_eq("2017", 30, ITEM_FUTBOL_FAFI),
				_eq("2016", 40, ITEM_FUTBOL_FAFI),
				_eq("2014", 50, ITEM_FUTBOL_FAFI),
				_eq("2013", 60, ITEM_FUTBOL_FAFI),
				_eq("2012", 70, ITEM_FUTBOL_FAFI),
			),
		),
		GrupoSeed(
			"TABI A",
			20,
			item_code=ITEM_FUTBOL_TABI_A,
			equipos=(
				_eq("2019", 10, ITEM_FUTBOL_TABI_A),
				_eq("2018", 20, ITEM_FUTBOL_TABI_A),
				_eq("2017", 30, ITEM_FUTBOL_TABI_A),
				_eq("2016", 40, ITEM_FUTBOL_TABI_A),
				_eq("2014", 50, ITEM_FUTBOL_TABI_A),
				_eq("2013", 60, ITEM_FUTBOL_TABI_A),
			),
		),
		GrupoSeed(
			GRUPO_FUTBOL_ESCUELITA,
			30,
			item_code=ITEM_FUTBOL_TABI_B,
			equipos=(
				_eq("2014/2015", 10, ITEM_FUTBOL_TABI_B),
				_eq("2016/2017", 20, ITEM_FUTBOL_TABI_B),
				_eq("2018/2019", 30, ITEM_FUTBOL_TABI_B),
				_eq("2020/2021", 40, ITEM_FUTBOL_TABI_B),
			),
		),
	),
)


ESTRUCTURA_PATIN = ActividadEstructuraSeed(
	"Patin Artistico",
	(
		GrupoSeed(
			"Patin Avanzado",
			10,
			item_code=ITEM_PATIN_AVANZADO,
			equipos=(
				_eq("A", 10, ITEM_PATIN_AVANZADO),
				_eq("B", 20, ITEM_PATIN_AVANZADO),
				_eq("C1", 30, ITEM_PATIN_AVANZADO),
				_eq("C2", 40, ITEM_PATIN_AVANZADO),
			),
		),
		GrupoSeed(
			"Patin Intermedio",
			20,
			item_code=ITEM_PATIN_INTERMEDIO,
			equipos=(
				_eq("1", 10, ITEM_PATIN_INTERMEDIO),
				_eq("2", 20, ITEM_PATIN_INTERMEDIO),
			),
		),
		_grupo_leaf("Patin Mini", 30, ITEM_PATIN_MINI),
		_grupo_leaf("Patin Teens", 40, ITEM_PATIN_TEENS),
		_grupo_leaf("Adulto", 45, ITEM_PATIN_ADULTO),
		_grupo_leaf("Patin Danza", 50, ITEM_PATIN_DANZA),
	),
)

ESTRUCTURA_GIMNASIA_ARTISTICA = ActividadEstructuraSeed(
	"Gimnasia Artistica",
	(
		_grupo_leaf("1 Clase por Semana", 10, ITEM_GIMNASIA_1_CLASE),
		_grupo_leaf("2 Clases por Semana", 20, ITEM_GIMNASIA_2_CLASES),
	),
)

ESTRUCTURA_BOXEO = ActividadEstructuraSeed(
	"Boxeo",
	(
		_grupo_leaf("1 Clase por Semana", 10, ITEM_BOXEO_1_CLASE),
		_grupo_leaf("2 Clases por Semana", 20, ITEM_BOXEO_2_CLASES),
		_grupo_leaf("3 Clases por Semana", 30, ITEM_BOXEO_3_CLASES),
	),
)

ESTRUCTURA_YOGA = ActividadEstructuraSeed(
	"Yoga",
	(
		_grupo_leaf("1 Clase por Semana", 10, ITEM_YOGA_1_CLASE),
		_grupo_leaf("2 Clases por Semana", 20, ITEM_YOGA_2_CLASES),
	),
)

ESTRUCTURA_GIMNASIO_FITNESS = ActividadEstructuraSeed(
	"Gimnasio Fitness",
	(
		_grupo_leaf("No Socio", 10, ITEM_GYM_NO_SOCIO),
		_grupo_leaf("Socio", 20, ITEM_GYM_SOCIO),
	),
)

ESTRUCTURA_INICIACION_DEPORTIVA = ActividadEstructuraSeed(
	"Iniciacion Deportiva",
	(
		_grupo_leaf("1 Clase por Semana", 10, ITEM_INICIACION_1_CLASE),
		_grupo_leaf("2 Clases por Semana", 20, ITEM_INICIACION_2_CLASES),
	),
)

ESTRUCTURA_FUNCIONAL = ActividadEstructuraSeed(
	"Funcional",
	(
		_grupo_leaf("GAP 1 vez/sem - Prof Noelia", 10, ITEM_FUNCIONAL_1_CLASE),
		_grupo_leaf("GAP 2 veces/sem - Prof Noelia", 20, ITEM_FUNCIONAL_2_CLASES),
		_grupo_leaf("CROSSFIT 1 vez/sem - Prof Noelia", 30, ITEM_FUNCIONAL_1_CLASE),
		_grupo_leaf("CROSSFIT 2 veces/sem - Prof Noelia", 40, ITEM_FUNCIONAL_2_CLASES),
		_grupo_leaf("Funcional 1 vez/sem - Prof Facundo", 50, ITEM_FUNCIONAL_1_CLASE),
		_grupo_leaf("Funcional 2 veces/sem - Prof Facundo", 60, ITEM_FUNCIONAL_2_CLASES),
	),
)


ESTRUCTURA_CON_GRUPOS: tuple[ActividadEstructuraSeed, ...] = (
	ESTRUCTURA_BASQUET,
	ESTRUCTURA_VOLEY_FEMENINO,
	ESTRUCTURA_FUTBOL,
	ESTRUCTURA_PATIN,
	ESTRUCTURA_GIMNASIA_ARTISTICA,
	ESTRUCTURA_INICIACION_DEPORTIVA,
	ESTRUCTURA_BOXEO,
	ESTRUCTURA_YOGA,
	ESTRUCTURA_GIMNASIO_FITNESS,
	ESTRUCTURA_FUNCIONAL,
)
