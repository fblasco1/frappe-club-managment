"""Normalización de fechas, horas y motivo de partidos."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from frappe.utils import getdate

from club_management.spaces.fixtures.contract import (
	FixturePartido,
	LOCALIA_LOCAL,
	LOCALIA_VISITANTE,
)
from club_management.spaces.import_horarios import parse_horario

_DATE_DDMMYYYY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_DEFAULT_MATCH_MINUTES = 120
_FORMATIVAS_MATCH_MINUTES = 90
_LIGA_METRO_WARMUP_MINUTES = 60
_LIGA_METRO_MATCH_MINUTES = 90
_SUPERIOR_B_WARMUP_MINUTES = 30
_SUPERIOR_B_MATCH_MINUTES = 90

_FORMATIVAS_CATEGORIAS = frozenset(
	{
		"U9",
		"U11",
		"U13",
		"U15",
		"U17",
		"U21",
		"U9 Flex",
		"U11 Flex",
		"U13 Flex",
		"U15 Flex",
		"U17 Flex",
		"SUP Flex",
		"U9 Fem",
		"U11 Fem",
		"U13 Fem",
		"U15 Fem",
		"U17 Fem",
		"U21 Fem",
	}
)


def normalize_localia(value: str) -> str:
	text = (value or "").strip().lower()
	if text.startswith("visit"):
		return LOCALIA_VISITANTE
	if text.startswith("loc"):
		return LOCALIA_LOCAL
	return text or LOCALIA_LOCAL


def parse_fecha_iso(raw: str) -> str | None:
	"""Acepta ISO YYYY-MM-DD o DD/MM/YYYY (Sheet CM)."""
	text = (raw or "").strip()
	if not text:
		return None
	if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
		return text
	m = _DATE_DDMMYYYY.match(text)
	if m:
		day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
		try:
			return datetime(year, month, day).date().isoformat()
		except ValueError:
			return None
	try:
		return getdate(text).isoformat()
	except Exception:
		return None


def _time_to_str(hour: int, minute: int = 0, second: int = 0) -> str:
	return f"{hour:02d}:{minute:02d}:{second:02d}"


def _parse_time_parts(hora: str) -> tuple[int, int, int]:
	parts = hora.split(":")
	h = int(parts[0])
	m = int(parts[1]) if len(parts) > 1 else 0
	s = int(parts[2]) if len(parts) > 2 else 0
	return h, m, s


def shift_time(hora: str, minutes: int) -> str:
	"""Suma (o resta) minutos a una hora HH:MM:SS."""
	h, m, s = _parse_time_parts(hora)
	base = datetime(2000, 1, 1, h, m, s)
	end = base + timedelta(minutes=minutes)
	return end.strftime("%H:%M:%S")


def add_hours_to_time(hora: str, hours: int = 2) -> str:
	return shift_time(hora, hours * 60)


def parse_hora_desde(raw: str) -> str | None:
	text = (raw or "").strip()
	if not text:
		return None
	parsed = parse_horario(text)
	if parsed:
		return parsed[0]
	if re.match(r"^\d{1,2}:\d{2}$", text):
		return f"{text}:00"
	if re.match(r"^\d{1,2}:\d{2}:\d{2}$", text):
		return text
	return None


def parse_hora_hasta_explicita(raw_hasta: str) -> str | None:
	"""Parsea solo un fin de franja (no aplica ventana +2h de parse_horario)."""
	text = (raw_hasta or "").strip()
	if not text:
		return None
	if re.match(r"^\d{1,2}:\d{2}$", text):
		return f"{text}:00"
	if re.match(r"^\d{1,2}:\d{2}:\d{2}$", text):
		return text
	# "21 A 22" / "21-22" → tomar el fin
	parsed = parse_horario(text)
	if parsed and (" A " in text.upper() or "-" in text or "–" in text):
		return parsed[1]
	return None


def is_liga_metro(categoria: str) -> bool:
	return "liga metro" in (categoria or "").strip().lower()


def is_superior_b(categoria: str, tira: str) -> bool:
	cat = (categoria or "").strip().upper()
	tira_n = (tira or "").strip().upper()
	return cat in {"SUP", "SUPERIOR"} and tira_n == "B"


def is_formativa(categoria: str) -> bool:
	cat = (categoria or "").strip()
	if cat in _FORMATIVAS_CATEGORIAS:
		return True
	# Prefijos U + edad (p. ej. variantes futuras)
	return bool(re.match(r"^U\d{1,2}(\s|$|Fem|Flex)", cat, re.IGNORECASE))


def ventana_ocupacion_partido(
	kickoff: str,
	*,
	categoria: str = "",
	tira: str = "",
	hora_hasta_explicita: str = "",
) -> tuple[str, str]:
	"""Devuelve (hora_desde, hora_hasta) de bloqueo de cancha a partir del kickoff."""
	explicita = parse_hora_hasta_explicita(hora_hasta_explicita)
	if explicita:
		return kickoff, explicita

	warmup = 0
	match_min = _DEFAULT_MATCH_MINUTES
	if is_liga_metro(categoria):
		warmup = _LIGA_METRO_WARMUP_MINUTES
		match_min = _LIGA_METRO_MATCH_MINUTES
	elif is_superior_b(categoria, tira):
		warmup = _SUPERIOR_B_WARMUP_MINUTES
		match_min = _SUPERIOR_B_MATCH_MINUTES
	elif is_formativa(categoria):
		warmup = 0
		match_min = _FORMATIVAS_MATCH_MINUTES

	hora_desde = shift_time(kickoff, -warmup) if warmup else kickoff
	hora_hasta = shift_time(kickoff, match_min)
	return hora_desde, hora_hasta


def parse_hora_hasta(hora_desde: str, raw_hasta: str = "") -> str:
	"""Compat: hasta explícita o +2h (legacy). Preferir ventana_ocupacion_partido."""
	explicita = parse_hora_hasta_explicita(raw_hasta)
	if explicita:
		return explicita
	return add_hours_to_time(hora_desde)


def build_motivo(partido: FixturePartido) -> str:
	if partido.motivo:
		return partido.motivo
	parts: list[str] = []
	if partido.categoria:
		parts.append(partido.categoria)
	if partido.tira:
		parts.append(partido.tira)
	label = " ".join(parts).strip()
	if partido.rival:
		if label:
			return f"{label} vs {partido.rival}"
		return f"vs {partido.rival}"
	return label or "Partido"


def normalize_partido(raw: dict[str, Any]) -> FixturePartido | str:
	"""Devuelve FixturePartido o mensaje de error/omisión."""
	item = FixturePartido.from_mapping(raw)
	if not item.external_id:
		return "Sin ID externo (external_id / ID_PARTIDO)"
	fecha = parse_fecha_iso(item.fecha)
	if not fecha:
		return f"Fecha inválida: {item.fecha!r}"
	kickoff = parse_hora_desde(item.hora_desde)
	if not kickoff:
		return f"Hora inválida: {item.hora_desde!r}"
	hora_desde, hora_hasta = ventana_ocupacion_partido(
		kickoff,
		categoria=item.categoria,
		tira=item.tira,
		hora_hasta_explicita=item.hora_hasta,
	)
	localia = normalize_localia(item.localia)
	motivo = build_motivo(item)
	espacio = item.espacio
	if espacio is not None:
		espacio = str(espacio).strip() or None
	return FixturePartido(
		source=item.source,
		external_id=item.external_id,
		fecha=fecha,
		hora_desde=hora_desde,
		hora_hasta=hora_hasta,
		categoria=item.categoria,
		tira=item.tira,
		rival=item.rival,
		localia=localia,
		direccion=item.direccion,
		resultado=item.resultado,
		espacio=espacio,
		motivo=motivo,
	)
