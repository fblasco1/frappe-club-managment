"""Estructura operativa de actividades, grupos/tiras y equipos del club ICDPE.

Secretaría puede ajustar nombres e ítems en Desk; este módulo es la fuente para el patch de seed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Categorías de equipo habituales en divisiones formativas.
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
class GrupoSeed:
	titulo: str
	orden: int
	item_code: str | None = None
	"""`item_code` ERPNext del arancel de la tira (opcional hasta cargar Items)."""


@dataclass(frozen=True)
class ActividadEstructuraSeed:
	actividad: str
	grupos: tuple[GrupoSeed, ...]


# Tiras del básquet (masculino y femenino comparten nomenclatura operativa).
_TIRAS_BASQUET: tuple[GrupoSeed, ...] = (
	GrupoSeed("Tira Azul", 10, "ICDPE-ARANCEL-MENSUAL-basquet-tira-azul"),
	GrupoSeed("Tira Amarilla", 20, "ICDPE-ARANCEL-MENSUAL-basquet-tira-amarilla"),
	GrupoSeed("Tira Flex", 30, "ICDPE-ARANCEL-MENSUAL-basquet-tira-flex"),
	GrupoSeed("Primera Division B", 40, "ICDPE-ARANCEL-MENSUAL-basquet-primera-b"),
)

ESTRUCTURA_CON_GRUPOS: tuple[ActividadEstructuraSeed, ...] = (
	ActividadEstructuraSeed("Basquet Masculino", _TIRAS_BASQUET),
	ActividadEstructuraSeed(
		"Basquet Femenino",
		(
			GrupoSeed("Tira Azul", 10, "ICDPE-ARANCEL-MENSUAL-basquet-fem-tira-azul"),
			GrupoSeed("Tira Amarilla", 20, "ICDPE-ARANCEL-MENSUAL-basquet-fem-tira-amarilla"),
			GrupoSeed("Tira Flex", 30, "ICDPE-ARANCEL-MENSUAL-basquet-fem-tira-flex"),
			GrupoSeed("Primera Division B", 40, "ICDPE-ARANCEL-MENSUAL-basquet-fem-primera-b"),
		),
	),
	ActividadEstructuraSeed(
		"Voley Femenino",
		(
			GrupoSeed("Primera Division", 10, "ICDPE-ARANCEL-MENSUAL-voley-primera"),
			GrupoSeed("Segunda Division", 20, "ICDPE-ARANCEL-MENSUAL-voley-segunda"),
			GrupoSeed("Juveniles", 30, "ICDPE-ARANCEL-MENSUAL-voley-juveniles"),
		),
	),
	ActividadEstructuraSeed(
		"Futbol",
		(
			GrupoSeed("Primera Division", 10, "ICDPE-ARANCEL-MENSUAL-futbol-primera"),
			GrupoSeed("Reserva", 20, "ICDPE-ARANCEL-MENSUAL-futbol-reserva"),
			GrupoSeed("Juveniles", 30, "ICDPE-ARANCEL-MENSUAL-futbol-juveniles"),
			GrupoSeed("Femenino", 40, "ICDPE-ARANCEL-MENSUAL-futbol-femenino"),
		),
	),
)
