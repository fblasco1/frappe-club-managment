"""Disponibilidad de espacios: grilla semanal vs reservas confirmadas."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_time, getdate

from club_management.spaces.planilla import TIPOS_SESION

DIAS_SEMANA: tuple[str, ...] = (
	"Lunes",
	"Martes",
	"Miercoles",
	"Jueves",
	"Viernes",
	"Sabado",
	"Domingo",
)

_WEEKDAY_TO_DIA: dict[int, str] = {i: nombre for i, nombre in enumerate(DIAS_SEMANA)}


def dia_semana_de_fecha(fecha: date | str) -> str:
	"""Nombre de día (Lunes…Domingo) para una fecha."""
	return _WEEKDAY_TO_DIA[getdate(fecha).weekday()]


def _as_time(value: Any) -> time:
	if isinstance(value, timedelta):
		total = int(value.total_seconds())
		hours, rem = divmod(total, 3600)
		minutes, seconds = divmod(rem, 60)
		return time(hours % 24, minutes, seconds)
	if isinstance(value, datetime):
		return value.time()
	if isinstance(value, time):
		return value
	return get_time(value)


def _minutes_of_day(value: Any) -> int:
	t = _as_time(value)
	return t.hour * 60 + t.minute


def _interval_minutes(start: Any, end: Any) -> tuple[int, int]:
	"""Minutos [desde, hasta) en un mismo día; si hasta <= desde, cruza medianoche."""
	start_min = _minutes_of_day(start)
	end_min = _minutes_of_day(end)
	if end_min <= start_min:
		end_min += 24 * 60
	return start_min, end_min


def intervals_overlap(start_a: Any, end_a: Any, start_b: Any, end_b: Any) -> bool:
	"""Solape estricto [a,b) vs [c,d): extremos iguales no solapan."""
	a0, a1 = _interval_minutes(start_a, end_a)
	b0, b1 = _interval_minutes(start_b, end_b)
	return a0 < b1 and b0 < a1


def validate_time_range(hora_desde: Any, hora_hasta: Any) -> None:
	if _as_time(hora_desde) == _as_time(hora_hasta):
		frappe.throw(_("hora_hasta debe ser mayor que hora_desde"), frappe.ValidationError)


def get_active_excepciones_for_date(fecha: date | str) -> list[dict[str, Any]]:
	"""Excepciones Activas del día (omiten grilla origen y ocupan destino)."""
	return frappe.get_all(
		"Excepcion Horario Dia",
		filters={"fecha": getdate(fecha), "estado": "Activa"},
		fields=[
			"name",
			"espacio_origen",
			"horario_row",
			"titulo_origen",
			"accion",
			"espacio_destino",
			"hora_desde",
			"hora_hasta",
			"motivo",
		],
	)


def expand_grid_for_date(espacio: str, fecha: date | str) -> list[dict[str, Any]]:
	"""Expande la grilla semanal del espacio al día de la fecha.

	Omite filas con `Excepcion Horario Dia` Activa ese día.
	"""
	dia = dia_semana_de_fecha(fecha)
	if not frappe.db.exists("Espacio", espacio):
		return []
	skipped = {
		(e.horario_row or "").strip()
		for e in get_active_excepciones_for_date(fecha)
		if e.espacio_origen == espacio
	}
	doc = frappe.get_doc("Espacio", espacio)
	slots: list[dict[str, Any]] = []
	for row in doc.get("horarios") or []:
		if row.dia_semana != dia:
			continue
		if row.name in skipped:
			continue
		slots.append(
			{
				"source": "horario",
				"dia_semana": row.dia_semana,
				"hora_desde": row.hora_desde,
				"hora_hasta": row.hora_hasta,
				"titulo": row.titulo,
				"tipo_sesion": getattr(row, "tipo_sesion", None),
				"actividad": row.actividad,
				"grupo_actividad": row.grupo_actividad,
				"equipo_actividad": row.equipo_actividad,
				"row_name": row.name,
			}
		)
	return slots


def expand_excepciones_for_date(espacio: str, fecha: date | str) -> list[dict[str, Any]]:
	"""Bloques excepcionales que ocupan `espacio` ese día (destino)."""
	out: list[dict[str, Any]] = []
	for exc in get_active_excepciones_for_date(fecha):
		if exc.espacio_destino != espacio:
			continue
		if (exc.get("accion") or "Reubicar").strip() == "Suspender":
			continue
		titulo = exc.titulo_origen or exc.motivo or _("Entrenamiento reubicado")
		out.append(
			{
				"source": "excepcion",
				"name": exc.name,
				"hora_desde": exc.hora_desde,
				"hora_hasta": exc.hora_hasta,
				"titulo": titulo,
				"motivo": exc.motivo,
				"horario_row": exc.horario_row,
				"espacio_origen": exc.espacio_origen,
			}
		)
	return out


def get_confirmed_reservations(
	espacio: str,
	fecha: date | str,
	*,
	exclude: str | None = None,
) -> list[dict[str, Any]]:
	"""Reservas Confirmada del espacio que ocupan la fecha (puntual o recurrente)."""
	from club_management.spaces.services.suspension_reserva import (
		get_suspended_reserva_names_for_date,
	)

	target = getdate(fecha)
	dia = dia_semana_de_fecha(target)
	suspended = get_suspended_reserva_names_for_date(str(target))
	rows = frappe.get_all(
		"Reserva Espacio",
		filters={"espacio": espacio, "estado": "Confirmada"},
		fields=[
			"name",
			"hora_desde",
			"hora_hasta",
			"tipo",
			"motivo",
			"modalidad_alquiler",
			"fecha",
			"fecha_desde",
			"fecha_hasta",
			"recurrencia_semanal",
		],
	)
	out: list[dict[str, Any]] = []
	for row in rows:
		if exclude and row.name == exclude:
			continue
		if row.name in suspended:
			continue
		if _reserva_ocupa_fecha(row, target, dia):
			out.append(row)
	return out


def _reserva_es_recurrente(row: dict[str, Any]) -> bool:
	modalidad = (row.get("modalidad_alquiler") or "").strip()
	if row.get("tipo") == "Alquiler externo" and modalidad == "Recurrente":
		return True
	return bool(row.get("tipo") == "Evento club" and row.get("recurrencia_semanal"))


def _reserva_ocupa_fecha(row: dict[str, Any], target: date, dia: str) -> bool:
	"""True si la reserva (puntual o recurrente) cae en `target`."""
	if _reserva_es_recurrente(row):
		desde = row.get("fecha_desde")
		hasta = row.get("fecha_hasta")
		if not desde or not hasta:
			return False
		if getdate(desde) > target or getdate(hasta) < target:
			return False
		dias = {
			d.dia_semana
			for d in frappe.get_all(
				"Reserva Espacio Dia",
				filters={"parent": row.name, "parenttype": "Reserva Espacio"},
				fields=["dia_semana"],
			)
		}
		return dia in dias
	# Puntual (incluye Temporal y tipos internos)
	if not row.get("fecha"):
		return False
	return getdate(row.fecha) == target


def iter_recurrence_dates(
	fecha_desde: date | str,
	fecha_hasta: date | str,
	dias: set[str] | list[str],
	*,
	max_days: int = 400,
) -> list[date]:
	"""Lista fechas del rango que coinciden con los días (cap de seguridad)."""
	start = getdate(fecha_desde)
	end = getdate(fecha_hasta)
	if end < start:
		frappe.throw(_("fecha_hasta debe ser mayor o igual a fecha_desde"), frappe.ValidationError)
	if (end - start).days > max_days:
		frappe.throw(
			_("El rango de alquiler recurrente no puede superar {0} días").format(max_days),
			frappe.ValidationError,
		)
	wanted = set(dias)
	out: list[date] = []
	cur = start
	one = timedelta(days=1)
	while cur <= end:
		if dia_semana_de_fecha(cur) in wanted:
			out.append(cur)
		cur = cur + one
	return out


def assert_recurring_no_overlap(
	espacio: str,
	fecha_desde: date | str,
	fecha_hasta: date | str,
	dias: set[str] | list[str],
	hora_desde: Any,
	hora_hasta: Any,
	*,
	exclude_reserva: str | None = None,
) -> None:
	"""Valida ocupación en cada ocurrencia del patrón recurrente."""
	for occ in iter_recurrence_dates(fecha_desde, fecha_hasta, dias):
		assert_no_overlap_with_occupancy(
			espacio,
			occ,
			hora_desde,
			hora_hasta,
			exclude_reserva=exclude_reserva,
		)


def get_occupancy(espacio: str, fecha: date | str) -> list[dict[str, Any]]:
	"""Slots ocupados: grilla del día + excepciones + reservas confirmadas."""
	occupancy = expand_grid_for_date(espacio, fecha)
	occupancy.extend(expand_excepciones_for_date(espacio, fecha))
	for res in get_confirmed_reservations(espacio, fecha):
		occupancy.append(
			{
				"source": "reserva",
				"name": res.name,
				"hora_desde": res.hora_desde,
				"hora_hasta": res.hora_hasta,
				"tipo": res.tipo,
				"motivo": res.motivo,
			}
		)
	return occupancy


def find_occupancy_conflicts(
	espacio: str,
	fecha: date | str,
	hora_desde: Any,
	hora_hasta: Any,
	*,
	exclude_reserva: str | None = None,
) -> list[dict[str, Any]]:
	"""Lista solapes con grilla semanal u otras reservas Confirmada (sin lanzar error)."""
	validate_time_range(hora_desde, hora_hasta)
	conflicts: list[dict[str, Any]] = []
	for slot in expand_grid_for_date(espacio, fecha):
		if intervals_overlap(hora_desde, hora_hasta, slot["hora_desde"], slot["hora_hasta"]):
			conflicts.append(
				{
					"tipo": "horario",
					"ref": slot.get("row_name"),
					"titulo": slot.get("titulo") or slot.get("tipo_sesion") or _("Entrenamiento"),
					"hora_desde": slot["hora_desde"],
					"hora_hasta": slot["hora_hasta"],
				}
			)
	for slot in expand_excepciones_for_date(espacio, fecha):
		if intervals_overlap(hora_desde, hora_hasta, slot["hora_desde"], slot["hora_hasta"]):
			conflicts.append(
				{
					"tipo": "excepcion",
					"ref": slot.get("name"),
					"titulo": slot.get("titulo") or _("Entrenamiento reubicado"),
					"hora_desde": slot["hora_desde"],
					"hora_hasta": slot["hora_hasta"],
				}
			)
	for res in get_confirmed_reservations(espacio, fecha, exclude=exclude_reserva):
		if intervals_overlap(hora_desde, hora_hasta, res.hora_desde, res.hora_hasta):
			conflicts.append(
				{
					"tipo": "reserva",
					"ref": res.name,
					"titulo": res.motivo or res.tipo or _("Reserva"),
					"hora_desde": res.hora_desde,
					"hora_hasta": res.hora_hasta,
				}
			)
	return conflicts


def assert_no_overlap_with_reservations_only(
	espacio: str,
	fecha: date | str,
	hora_desde: Any,
	hora_hasta: Any,
	*,
	exclude_reserva: str | None = None,
) -> None:
	"""Lanza ValidationError si solapa otra reserva Confirmada (sin considerar grilla)."""
	validate_time_range(hora_desde, hora_hasta)
	for res in get_confirmed_reservations(espacio, fecha, exclude=exclude_reserva):
		if intervals_overlap(hora_desde, hora_hasta, res.hora_desde, res.hora_hasta):
			frappe.throw(
				_("El horario se solapa con la reserva confirmada {0}").format(res.name),
				frappe.ValidationError,
			)


def assert_no_overlap_with_occupancy(
	espacio: str,
	fecha: date | str,
	hora_desde: Any,
	hora_hasta: Any,
	*,
	exclude_reserva: str | None = None,
) -> None:
	"""Lanza ValidationError si el intervalo solapa ocupación existente."""
	validate_time_range(hora_desde, hora_hasta)
	slots = expand_grid_for_date(espacio, fecha)
	slots.extend(expand_excepciones_for_date(espacio, fecha))
	for res in get_confirmed_reservations(espacio, fecha, exclude=exclude_reserva):
		slots.append(
			{
				"source": "reserva",
				"name": res.name,
				"hora_desde": res.hora_desde,
				"hora_hasta": res.hora_hasta,
			}
		)
	for slot in slots:
		if intervals_overlap(hora_desde, hora_hasta, slot["hora_desde"], slot["hora_hasta"]):
			frappe.throw(
				_("El horario se solapa con ocupación existente del espacio {0}").format(espacio),
				frappe.ValidationError,
			)


def assert_grid_compatible_with_confirmed_reservations(
	espacio_name: str,
	horarios: list[Any],
) -> None:
	"""Al guardar la grilla, rechaza si solapa reservas Confirmada (puntual o recurrente)."""
	by_day: dict[str, list[Any]] = {}
	for row in horarios or []:
		by_day.setdefault(row.dia_semana, []).append(row)
	if not by_day:
		return

	# Tomar un rango de referencia: próximas 8 semanas desde hoy
	today = getdate()
	for offset in range(0, 56):
		target = today + timedelta(days=offset)
		dia = dia_semana_de_fecha(target)
		rows_dia = by_day.get(dia) or []
		if not rows_dia:
			continue
		for res in get_confirmed_reservations(espacio_name, target):
			for row in rows_dia:
				if intervals_overlap(row.hora_desde, row.hora_hasta, res.hora_desde, res.hora_hasta):
					frappe.throw(
						_("La grilla solapa la reserva confirmada {0} del {1}").format(
							res.name, target
						),
						frappe.ValidationError,
					)


def assert_horarios_table_valid_ranges(horarios: list[Any]) -> None:
	"""Valida solo rangos (hasta > desde). Varios equipos pueden solapar en la misma cancha."""
	for row in horarios or []:
		validate_time_range(row.hora_desde, row.hora_hasta)


def validate_activity_links(
	actividad: str | None,
	grupo_actividad: str | None,
	equipo_actividad: str | None,
) -> None:
	"""Exige coherencia Actividad → Grupo → Equipo cuando hay vínculos."""
	if equipo_actividad:
		grupo = frappe.db.get_value("Equipo Actividad", equipo_actividad, "grupo_actividad")
		if not grupo:
			frappe.throw(_("Equipo Actividad inválido"), frappe.ValidationError)
		if grupo_actividad and grupo_actividad != grupo:
			frappe.throw(
				_("El equipo no pertenece al grupo indicado"),
				frappe.ValidationError,
			)
		grupo_actividad = grupo_actividad or grupo
		act = frappe.db.get_value("Grupo Actividad", grupo, "actividad")
		if actividad and act and actividad != act:
			frappe.throw(
				_("El equipo no pertenece a la actividad indicada"),
				frappe.ValidationError,
			)

	if grupo_actividad:
		act = frappe.db.get_value("Grupo Actividad", grupo_actividad, "actividad")
		if actividad and act and actividad != act:
			frappe.throw(
				_("El grupo no pertenece a la actividad indicada"),
				frappe.ValidationError,
			)


def _display_titulo(doctype: str, name: str | None) -> str:
	if not name:
		return ""
	titulo = frappe.db.get_value(doctype, name, "titulo")
	return str(titulo or name)


def build_horario_titulo(
	actividad: str | None,
	grupo_actividad: str | None,
	equipo_actividad: str | None,
	*,
	tipo_sesion: str | None = None,
	etiqueta: str | None = None,
) -> str:
	"""Concatena tipo de sesión + Actividad / Grupo / Equipo o etiqueta libre."""
	parts: list[str] = []
	act = _display_titulo("Actividad", actividad)
	if act:
		parts.append(act)
	grp = _display_titulo("Grupo Actividad", grupo_actividad)
	if grp:
		parts.append(grp)
	eq = _display_titulo("Equipo Actividad", equipo_actividad)
	if eq:
		parts.append(eq)
	label = (etiqueta or "").strip()
	if label and not parts:
		cuerpo = label
	elif parts:
		cuerpo = " / ".join(parts)
	elif label:
		cuerpo = label
	else:
		cuerpo = ""
	tipo = (tipo_sesion or "").strip()
	if tipo and cuerpo:
		return f"{tipo} — {cuerpo}"
	if tipo:
		return tipo
	return cuerpo
