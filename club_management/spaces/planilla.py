"""Catálogo de tipos de evento y orden de columnas de la planilla de ocupación."""

from __future__ import annotations

from typing import Any

CANCHA_1 = "Arq. Horacio Esteban Antoliche - Cancha 1"
CANCHA_2 = "Jose Capano - Cancha 2"
CANCHA_3 = "Jorge Horacio Antoliche - Cancha 3"

# Tipos de sesión en grilla semanal (Horario Entrenamiento)
TIPOS_SESION: tuple[str, ...] = (
	"Preparacion Fisica",
	"Entrenamiento",
)

# Tipos de Reserva Espacio
TIPOS_RESERVA: tuple[str, ...] = (
	"Alquiler externo",
	"Alquiler socio",
	"Evento club",
	"Bloqueo",
)

TIPOS_EVENTO_PLANILLA: tuple[str, ...] = TIPOS_SESION + TIPOS_RESERVA

_LEGACY_TIPO_SESION: dict[str, str] = {
	"Preparación física": "Preparacion Fisica",
	"Entrenamiento deportivo": "Entrenamiento",
}

_LEGACY_TIPO_RESERVA: dict[str, str] = {
	"Uso interno": "Alquiler socio",
}

ESPACIO_ORDEN_PLANILLA: tuple[str, ...] = (
	CANCHA_1,
	CANCHA_2,
	CANCHA_3,
	"GIMNASIO BAJO TRIBUNA",
	"SALON P.B.",
	"SUM P.B.",
	"SUBSUELO",
	"SALA ALBAMONTE",
	"PARRILLA - TERRAZA",
	"LA CASONA",
)

TITULO_PLANILLA: dict[str, str] = {
	CANCHA_1: "Cancha 1",
	CANCHA_2: "Cancha 2",
	CANCHA_3: "Cancha 3",
	"GIMNASIO BAJO TRIBUNA": "Gimnasio Bajo Tribuna",
	"SALON P.B.": "SALON PB",
	"SUM P.B.": "SUM PB",
	"SUBSUELO": "SUBSUELO",
	"SALA ALBAMONTE": "SALA ALBAMONTE",
	"PARRILLA - TERRAZA": "PARRILLA/TERRAZA",
	"LA CASONA": "LA CASONA",
}

_COLOR_PF = "#f4c784"
_COLOR_ENTRENAMIENTO = "#f5a3c7"
_COLOR_ALQUILER_EXTERNO = "#7ec8e3"
_COLOR_ALQUILER_SOCIO = "#ffe08a"
_COLOR_EVENTO = "#b8e986"
_COLOR_BLOQUEO = "#cfcfcf"
_COLOR_DEFAULT = "#d0d7de"
_COLOR_SUPERPOSICION = "#e74c3c"
_COLOR_EXCEPCION = "#9b59b6"

COLOR_POR_TIPO: dict[str, str] = {
	"Preparacion Fisica": _COLOR_PF,
	"Entrenamiento": _COLOR_ENTRENAMIENTO,
	"Alquiler externo": _COLOR_ALQUILER_EXTERNO,
	"Alquiler socio": _COLOR_ALQUILER_SOCIO,
	"Evento club": _COLOR_EVENTO,
	"Bloqueo": _COLOR_BLOQUEO,
}


def normalize_tipo_sesion(value: str | None) -> str:
	raw = (value or "").strip()
	if not raw:
		return ""
	return _LEGACY_TIPO_SESION.get(raw, raw)


def normalize_tipo_reserva(value: str | None) -> str:
	raw = (value or "").strip()
	if not raw:
		return ""
	return _LEGACY_TIPO_RESERVA.get(raw, raw)


def categoria_evento(block: dict[str, Any]) -> str:
	source = block.get("source")
	if source == "excepcion":
		return "Reubicado"
	if source == "reserva":
		return normalize_tipo_reserva(block.get("tipo")) or "Reserva"
	return normalize_tipo_sesion(block.get("tipo_sesion")) or "Entrenamiento"


def color_for_block(block: dict[str, Any]) -> str:
	if block.get("superposicion"):
		return _COLOR_SUPERPOSICION
	source = block.get("source")
	if source == "excepcion":
		return _COLOR_EXCEPCION
	categoria = categoria_evento(block)
	return COLOR_POR_TIPO.get(categoria, _COLOR_DEFAULT)


def leyenda_planilla() -> list[dict[str, str]]:
	return [
		{"label": "Entrenamiento", "color": _COLOR_ENTRENAMIENTO},
		{"label": "Preparacion Fisica", "color": _COLOR_PF},
		{"label": "Alquiler externo", "color": _COLOR_ALQUILER_EXTERNO},
		{"label": "Alquiler socio", "color": _COLOR_ALQUILER_SOCIO},
		{"label": "Evento club", "color": _COLOR_EVENTO},
		{"label": "Bloqueo", "color": _COLOR_BLOQUEO},
		{"label": "Reubicado (solo este día)", "color": _COLOR_EXCEPCION},
		{"label": "Superposición (revisar)", "color": _COLOR_SUPERPOSICION},
	]


def sort_espacios_planilla(espacios: list[dict[str, Any]]) -> list[dict[str, Any]]:
	order = {name: idx for idx, name in enumerate(ESPACIO_ORDEN_PLANILLA)}
	out: list[dict[str, Any]] = []
	for esp in espacios:
		item = dict(esp)
		name = str(item.get("name") or "")
		item["titulo_planilla"] = TITULO_PLANILLA.get(name, item.get("titulo") or name)
		out.append(item)
	out.sort(
		key=lambda esp: (
			order.get(str(esp.get("name") or ""), len(order)),
			str(esp.get("titulo_planilla") or esp.get("name") or ""),
		)
	)
	return out
