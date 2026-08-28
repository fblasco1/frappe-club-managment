"""Payload del dashboard de ocupación de espacios (planilla 08:00–04:00)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, today

from club_management.spaces.availability import (
	_as_time,
	dia_semana_de_fecha,
	get_occupancy,
)
from club_management.spaces.planilla import (
	categoria_evento,
	color_for_block,
	leyenda_planilla,
	sort_espacios_planilla,
)

# Ventana: 08:00 del día D hasta 04:00 del día D+1
WINDOW_START_MIN = 8 * 60
WINDOW_END_MIN = 24 * 60 + 4 * 60  # 28*60 = 1680
SLOT_MINUTES = 30

_COLOR_SUPERPOSICION = "#e74c3c"


def _minutes_of_day(value: Any) -> int:
	t = _as_time(value)
	return t.hour * 60 + t.minute


def _fmt_hhmm(total_min: int) -> str:
	"""Minutos desde 00:00 del día D (puede ser >= 1440)."""
	m = total_min % (24 * 60)
	return f"{m // 60:02d}:{m % 60:02d}"


def build_time_slots() -> list[str]:
	"""Etiquetas de inicio de cada franja de 30 min en la ventana."""
	slots: list[str] = []
	m = WINDOW_START_MIN
	while m < WINDOW_END_MIN:
		slots.append(_fmt_hhmm(m))
		m += SLOT_MINUTES
	return slots


def _clip_interval(start: int, end: int) -> tuple[int, int] | None:
	"""Recorta [start,end) a la ventana [WINDOW_START_MIN, WINDOW_END_MIN)."""
	s = max(start, WINDOW_START_MIN)
	e = min(end, WINDOW_END_MIN)
	if e <= s:
		return None
	return s, e


def _interval_from_times(hora_desde: Any, hora_hasta: Any, *, day_offset: int) -> tuple[int, int]:
	"""Convierte horas a minutos absolutos desde 00:00 del día D (+ day_offset*1440)."""
	base = day_offset * 24 * 60
	start = base + _minutes_of_day(hora_desde)
	end = base + _minutes_of_day(hora_hasta)
	if end <= start:
		# Cruza medianoche dentro del mismo registro
		end += 24 * 60
	return start, end


def _enrich_horario_slot(raw: dict[str, Any], espacio_name: str) -> dict[str, Any]:
	out = dict(raw)
	out["espacio"] = espacio_name
	if not out.get("tipo_sesion") and out.get("row_name"):
		out["tipo_sesion"] = frappe.db.get_value(
			"Horario Entrenamiento", out["row_name"], "tipo_sesion"
		)
	if not out.get("titulo"):
		if out.get("source") == "excepcion":
			out["titulo"] = out.get("motivo") or _("Entrenamiento reubicado")
		else:
			parts = [
				p
				for p in (
					out.get("tipo_sesion"),
					out.get("actividad"),
					out.get("grupo_actividad"),
					out.get("equipo_actividad"),
				)
				if p
			]
			out["titulo"] = " / ".join(str(p) for p in parts) if parts else _("Ocupado")
	return out


def _blocks_for_espacio(espacio_name: str, fecha: date) -> list[dict[str, Any]]:
	"""Bloques de ocupación del espacio en la ventana del día `fecha`."""
	bloques: list[dict[str, Any]] = []
	next_day = fecha + timedelta(days=1)

	for raw in get_occupancy(espacio_name, fecha):
		item = (
			_enrich_horario_slot(raw, espacio_name)
			if raw.get("source") in {"horario", "excepcion"}
			else dict(raw)
		)
		item["espacio"] = espacio_name
		start, end = _interval_from_times(item["hora_desde"], item["hora_hasta"], day_offset=0)
		clipped = _clip_interval(start, end)
		if not clipped:
			continue
		s, e = clipped
		bloques.append(_finalize_block(item, s, e))

	for raw in get_occupancy(espacio_name, next_day):
		item = (
			_enrich_horario_slot(raw, espacio_name)
			if raw.get("source") in {"horario", "excepcion"}
			else dict(raw)
		)
		item["espacio"] = espacio_name
		start, end = _interval_from_times(item["hora_desde"], item["hora_hasta"], day_offset=1)
		clipped = _clip_interval(start, end)
		if not clipped:
			continue
		s, e = clipped
		if s >= 24 * 60:
			bloques.append(_finalize_block(item, s, e))

	return bloques


def _finalize_block(item: dict[str, Any], start_min: int, end_min: int) -> dict[str, Any]:
	titulo = item.get("titulo") or item.get("motivo") or item.get("name") or ""
	block = {
		"espacio": item.get("espacio"),
		"titulo": str(titulo),
		"source": item.get("source"),
		"tipo": item.get("tipo"),
		"tipo_sesion": item.get("tipo_sesion"),
		"ref": item.get("name") or item.get("row_name"),
		"horario_row": item.get("row_name") or item.get("horario_row"),
		"inicio": _fmt_hhmm(start_min),
		"fin": _fmt_hhmm(end_min),
		"inicio_min": start_min,
		"fin_min": end_min,
	}
	block["categoria"] = categoria_evento(block)
	block["color"] = color_for_block(block)
	return block


def _intervals_overlap_min(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
	return start_a < end_b and start_b < end_a


def _mark_superposiciones(bloques: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Marca bloques que se solapan en el mismo espacio (grilla vs partido, etc.)."""
	for i, bloque_a in enumerate(bloques):
		for bloque_b in bloques[i + 1 :]:
			if bloque_a.get("espacio") != bloque_b.get("espacio"):
				continue
			if _intervals_overlap_min(
				bloque_a["inicio_min"],
				bloque_a["fin_min"],
				bloque_b["inicio_min"],
				bloque_b["fin_min"],
			):
				bloque_a["superposicion"] = True
				bloque_b["superposicion"] = True
				bloque_a["color"] = _COLOR_SUPERPOSICION
				bloque_b["color"] = _COLOR_SUPERPOSICION
	return bloques


def _collect_superposiciones_alertas(bloques: list[dict[str, Any]], fecha: date) -> list[str]:
	alertas: list[str] = []
	for i, bloque_a in enumerate(bloques):
		if not bloque_a.get("superposicion"):
			continue
		for bloque_b in bloques[i + 1 :]:
			if not bloque_b.get("superposicion"):
				continue
			if bloque_a.get("espacio") != bloque_b.get("espacio"):
				continue
			alertas.append(
				_("{0}: «{1}» ({2}–{3}) solapa con «{4}» ({5}–{6})").format(
					bloque_a.get("espacio"),
					bloque_a.get("titulo"),
					bloque_a.get("inicio"),
					bloque_a.get("fin"),
					bloque_b.get("titulo"),
					bloque_b.get("inicio"),
					bloque_b.get("fin"),
				)
			)
	# dedupe simétricos
	return list(dict.fromkeys(alertas))


def get_ocupacion_dashboard_payload(
	*,
	fecha: str | date | None = None,
) -> dict[str, Any]:
	"""Arma la planilla de ocupación para Desk."""
	ref = getdate(fecha or today())
	espacios = sort_espacios_planilla(
		frappe.get_all(
			"Espacio",
			filters={"habilitado": 1},
			fields=["name", "titulo", "tipo"],
		)
	)
	bloques: list[dict[str, Any]] = []
	for esp in espacios:
		bloques.extend(_blocks_for_espacio(esp["name"], ref))

	bloques = _mark_superposiciones(bloques)
	superposiciones = _collect_superposiciones_alertas(bloques, ref)

	return {
		"fecha": str(ref),
		"dia_semana": dia_semana_de_fecha(ref),
		"ventana": {"desde": "08:00", "hasta": "04:00", "slot_minutos": SLOT_MINUTES},
		"slots": build_time_slots(),
		"espacios": espacios,
		"bloques": bloques,
		"superposiciones": superposiciones,
		"leyenda": leyenda_planilla(),
	}
