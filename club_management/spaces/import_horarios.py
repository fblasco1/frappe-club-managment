"""Importación de grilla semanal desde CSV (Coordinación de espacios)."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frappe
from frappe import _

from club_management.spaces.availability import TIPOS_SESION, build_horario_titulo
from club_management.spaces.planilla import CANCHA_1, CANCHA_2, CANCHA_3

_DIA_MAP = {
	"LUNES": "Lunes",
	"MARTES": "Martes",
	"MIERCOLES": "Miercoles",
	"MIÉRCOLES": "Miercoles",
	"JUEVES": "Jueves",
	"VIERNES": "Viernes",
	"SABADO": "Sabado",
	"SÁBADO": "Sabado",
	"DOMINGO": "Domingo",
}

# En planillas operativas «GIMNASIO 1/2/3» = canchas ya cargadas en Desk.
CANCHA_BY_GIMNASIO_LABEL: dict[str, str] = {
	"GIMNASIO 1": CANCHA_1,
	"GIMNASIO 2": CANCHA_2,
	"GIMNASIO 3": CANCHA_3,
}

_ESPACIO_MAP: dict[str, str] = {
	**CANCHA_BY_GIMNASIO_LABEL,
	"GIM FISICO": "GIMNASIO BAJO TRIBUNA",
	"FISICO": "GIMNASIO BAJO TRIBUNA",
	"P.B. SALON": "SALON P.B.",
	"SALON P.B.": "SALON P.B.",
	"P.B. SUM": "SUM P.B.",
	"SUM P.B": "SUM P.B.",
	"SUM P.B.": "SUM P.B.",
	"SUBSUELO": "SUBSUELO",
	"SALA ALBAMONTE": "SALA ALBAMONTE",
	"LA CASONA": "LA CASONA",
}

_ACTIVIDAD_KEYWORDS: tuple[tuple[str, str], ...] = (
	("FUNCIONAL", "Funcional"),
	("BOXEO", "Boxeo"),
	("TAEKWONDO", "Taekwondo"),
	("YOGA", "Yoga"),
	("DANZA", "Danza"),
	("CROSSFIT", "Crossfit"),
	("GIMNASIA ARTISTICA", "Gimnasia Artistica"),
	("INICIACION DEPOR", "Iniciacion Deportiva"),
	("PATIN", "Patin Artistico"),
	("VOLEY", "Voley Femenino"),
	("BASQUET FEMENINO", "Basquet Femenino"),
	("ESCUELITA", "Basquet Escuelita"),
	("BASQUET", "Basquet"),
)

_EVENTO_CLUB_KEYWORDS: tuple[str, ...] = (
	"CENA",
	"VITALICIO",
	"JUBILADOS",
	"FIESTA",
	"ASADO",
)

_WEEKDAYS_LV = frozenset({"Lunes", "Martes", "Miercoles", "Jueves", "Viernes"})

_TIME_TOKEN = re.compile(
	r"(\d{1,2})"
	r"(?:[:.](\d{2}))?"
	r"(?:\s*HS)?",
	re.IGNORECASE,
)


@dataclass
class ImportRow:
	dia: str
	espacio: str
	hora_desde: str
	hora_hasta: str
	etiqueta: str
	tipo_sesion: str
	actividad: str | None = None
	es_alquiler: bool = False
	arrendatario: str | None = None
	es_evento_club: bool = False
	motivo_evento: str | None = None


@dataclass
class ImportReport:
	horarios_creados: int = 0
	reservas_creadas: int = 0
	eventos_club_creados: int = 0
	espacios_actualizados: list[str] = field(default_factory=list)
	omitidos: list[str] = field(default_factory=list)
	errores: list[str] = field(default_factory=list)


def ensure_espacios_csv() -> list[str]:
	"""Asegura catálogo base; GIMNASIO 1–3 del CSV son canchas ya existentes."""
	from club_management.spaces.seed import ensure_espacios_catalogo

	return ensure_espacios_catalogo()


def consolidate_gimnasio_canchas() -> list[str]:
	"""Elimina Espacio duplicados GIMNASIO 1/2/3 y reasigna reservas a las canchas."""
	removed: list[str] = []
	for wrong, cancha in CANCHA_BY_GIMNASIO_LABEL.items():
		if not frappe.db.exists("Espacio", wrong):
			continue
		if not frappe.db.exists("Espacio", cancha):
			frappe.throw(_("Cancha destino inexistente: {0}").format(cancha))
		frappe.db.set_value(
			"Reserva Espacio",
			{"espacio": wrong},
			"espacio",
			cancha,
			update_modified=False,
		)
		frappe.delete_doc("Espacio", wrong, force=1, ignore_permissions=True)
		removed.append(wrong)
	return removed


def _normalize_key(value: str) -> str:
	return " ".join((value or "").upper().split())


def map_espacio(raw: str) -> str | None:
	key = _normalize_key(raw)
	return _ESPACIO_MAP.get(key)


def map_dia(raw: str) -> str | None:
	return _DIA_MAP.get(_normalize_key(raw))


def _time_to_str(hour: int, minute: int = 0) -> str:
	return f"{hour:02d}:{minute:02d}:00"


def _parse_single_time(token: str) -> tuple[int, int] | None:
	token = token.strip().upper()
	if not token:
		return None
	m = _TIME_TOKEN.match(token)
	if not m:
		return None
	hour = int(m.group(1))
	minute = int(m.group(2) or 0)
	if hour >= 24 or minute >= 60:
		return None
	return hour, minute


def parse_horario(raw: str) -> tuple[str, str] | None:
	"""Parsea '08:15 A 12:15', '15 A 16', '13-17', 'DESDE 20.00', etc."""
	text = (raw or "").strip().upper()
	if not text:
		return None
	if text.startswith("DESDE "):
		text = text.replace("DESDE ", "", 1)
		start = _parse_single_time(text)
		if not start:
			return None
		return _time_to_str(*start), _time_to_str(start[0] + 2, start[1])

	# Rango con guión: 13-17, 13:00-17:00
	if "-" in text and not text.startswith("DESDE"):
		left, right = text.split("-", 1)
		s = _parse_single_time(left.strip())
		e = _parse_single_time(right.strip())
		if s and e:
			return _time_to_str(*s), _time_to_str(*e)

	# Separadores comunes
	for sep in (" A ", " – ", " — "):
		if sep in text:
			left, right = text.split(sep, 1)
			s = _parse_single_time(left.strip())
			e = _parse_single_time(right.strip())
			if s and e:
				return _time_to_str(*s), _time_to_str(*e)

	# Dos tokens pegados: "20:15 21:30"
	parts = re.split(r"\s+", text)
	if len(parts) >= 2:
		s = _parse_single_time(parts[0])
		e = _parse_single_time(parts[1])
		if s and e:
			return _time_to_str(*s), _time_to_str(*e)

	# Un solo horario (partido/evento sin fin explícito) — ventana 2h
	only = _parse_single_time(text)
	if only:
		end_h = min(only[0] + 2, 23)
		end_m = only[1]
		if end_h == 23 and end_m == 0:
			end_m = 30
		return _time_to_str(*only), _time_to_str(end_h, end_m)

	return None


def infer_tipo_sesion(espacio_raw: str, actividad: str) -> str:
	act = (actividad or "").upper()
	esp = _normalize_key(espacio_raw)
	if "FISICO" in act or esp in {"GIM FISICO", "FISICO"} or act.startswith("FISICO "):
		return "Preparacion Fisica"
	return "Entrenamiento"


def match_actividad(actividad: str) -> str | None:
	upper = (actividad or "").upper()
	for needle, name in _ACTIVIDAD_KEYWORDS:
		if needle in upper and frappe.db.exists("Actividad", name):
			return name
	return None


def is_evento_club_social(actividad: str) -> bool:
	"""True si la actividad CSV es un evento social del club (cena, jubilados, etc.)."""
	upper = (actividad or "").upper().strip()
	if not upper or upper.startswith("ALQ."):
		return False
	return any(keyword in upper for keyword in _EVENTO_CLUB_KEYWORDS)


def build_etiqueta(actividad: str, profesor: str) -> str:
	act = (actividad or "").strip()
	prof = (profesor or "").strip()
	if act and prof:
		return f"{act} — {prof}"
	return act or prof


def parse_csv_row(row: dict[str, str]) -> ImportRow | str:
	dia = map_dia(row.get("Dia") or row.get("Día") or "")
	espacio = map_espacio(row.get("Espacio") or "")
	if not dia:
		return _("Día no reconocido: {0}").format(row.get("Dia"))
	if not espacio:
		return _("Espacio no mapeado: {0}").format(row.get("Espacio"))

	actividad_raw = (row.get("Actividad") or "").strip()
	profesor = (row.get("Profesor") or "").strip()
	horario_raw = (row.get("Horario") or "").strip()

	# Filas con horario inválido pero actividad en columna Horario (ej. partidos)
	if not parse_horario(horario_raw) and actividad_raw:
		horario_raw, actividad_raw = actividad_raw, horario_raw

	times = parse_horario(horario_raw)
	if not times:
		return _("Horario no parseable: {0}").format(row.get("Horario"))

	hora_desde, hora_hasta = times
	etiqueta = build_etiqueta(actividad_raw, profesor)
	es_alquiler = actividad_raw.upper().startswith("ALQ.")

	if es_alquiler:
		arrendatario = actividad_raw.split(".", 1)[-1].strip() or actividad_raw
		return ImportRow(
			dia=dia,
			espacio=espacio,
			hora_desde=hora_desde,
			hora_hasta=hora_hasta,
			etiqueta=etiqueta,
			tipo_sesion="Entrenamiento",
			es_alquiler=True,
			arrendatario=arrendatario,
		)

	if is_evento_club_social(actividad_raw):
		return ImportRow(
			dia=dia,
			espacio=espacio,
			hora_desde=hora_desde,
			hora_hasta=hora_hasta,
			etiqueta=etiqueta,
			tipo_sesion="Evento club",
			es_evento_club=True,
			motivo_evento=actividad_raw.strip(),
		)

	return ImportRow(
		dia=dia,
		espacio=espacio,
		hora_desde=hora_desde,
		hora_hasta=hora_hasta,
		etiqueta=etiqueta,
		tipo_sesion=infer_tipo_sesion(row.get("Espacio") or "", actividad_raw),
		actividad=match_actividad(actividad_raw),
	)


def load_csv_rows(path: str | Path) -> list[ImportRow | str]:
	out: list[ImportRow | str] = []
	with open(path, newline="", encoding="utf-8-sig") as fh:
		reader = csv.DictReader(fh, delimiter=";")
		for row in reader:
			if not any((v or "").strip() for v in row.values()):
				continue
			out.append(parse_csv_row(row))
	return out


def _horario_row_dict(item: ImportRow) -> dict[str, Any]:
	tipo = item.tipo_sesion
	if tipo not in TIPOS_SESION:
		tipo = "Entrenamiento"
	payload: dict[str, Any] = {
		"dia_semana": item.dia,
		"hora_desde": item.hora_desde,
		"hora_hasta": item.hora_hasta,
		"tipo_sesion": tipo,
		"etiqueta": item.etiqueta,
	}
	if item.actividad:
		payload["actividad"] = item.actividad
	payload["titulo"] = build_horario_titulo(
		item.actividad,
		None,
		None,
		tipo_sesion=tipo,
		etiqueta=item.etiqueta,
	)
	return payload


def _reserva_recurrente_key(item: ImportRow) -> str:
	return f"{item.espacio}|{item.dia}|{item.hora_desde}|{item.hora_hasta}|{item.arrendatario}"


def _evento_club_recurrente_key(item: ImportRow) -> str:
	motivo = (item.motivo_evento or item.etiqueta or "").strip()
	return f"{item.espacio}|{item.dia}|{item.hora_desde}|{item.hora_hasta}|{motivo}"


def import_horarios_csv(
	path: str | Path,
	*,
	replace_weekdays: bool = True,
	replace_days: set[str] | frozenset[str] | None = None,
) -> dict[str, Any]:
	"""Importa horarios desde CSV. Alquileres ALQ.* → Reserva recurrente.

	`replace_days`: días a reemplazar (p. ej. {\"Sabado\"}).
	Si es None y `replace_weekdays`, reemplaza L–V.
	"""
	ensure_espacios_csv()
	consolidate_gimnasio_canchas()
	rows = load_csv_rows(path)
	report = ImportReport()

	days_to_replace: set[str] | None
	if replace_days is not None:
		days_to_replace = set(replace_days)
	elif replace_weekdays:
		days_to_replace = set(_WEEKDAYS_LV)
	else:
		days_to_replace = None

	horarios_by_espacio: dict[str, list[dict[str, Any]]] = {}
	reservas: list[ImportRow] = []
	eventos_club: list[ImportRow] = []

	for entry in rows:
		if isinstance(entry, str):
			report.omitidos.append(entry)
			continue
		if entry.es_alquiler:
			reservas.append(entry)
			continue
		if entry.es_evento_club:
			eventos_club.append(entry)
			continue
		horarios_by_espacio.setdefault(entry.espacio, []).append(_horario_row_dict(entry))

	espacios_solo_eventos: set[str] = set()
	if days_to_replace:
		for item in eventos_club:
			if item.dia in days_to_replace:
				espacios_solo_eventos.add(item.espacio)

	for espacio, new_rows in horarios_by_espacio.items():
		if not frappe.db.exists("Espacio", espacio):
			report.errores.append(_("Espacio inexistente: {0}").format(espacio))
			continue
		doc = frappe.get_doc("Espacio", espacio)
		if days_to_replace:
			keep = [
				r
				for r in (doc.get("horarios") or [])
				if r.dia_semana not in days_to_replace
			]
			doc.set("horarios", keep)
		for row in new_rows:
			doc.append("horarios", row)
			report.horarios_creados += 1
		doc.flags.skip_spaces_grid_reserva_check = True
		doc.save(ignore_permissions=True)
		if espacio not in report.espacios_actualizados:
			report.espacios_actualizados.append(espacio)

	for espacio in espacios_solo_eventos - set(horarios_by_espacio.keys()):
		if not frappe.db.exists("Espacio", espacio):
			report.errores.append(_("Espacio inexistente: {0}").format(espacio))
			continue
		doc = frappe.get_doc("Espacio", espacio)
		keep = [
			r
			for r in (doc.get("horarios") or [])
			if r.dia_semana not in days_to_replace
		]
		doc.set("horarios", keep)
		doc.flags.skip_spaces_grid_reserva_check = True
		doc.save(ignore_permissions=True)
		if espacio not in report.espacios_actualizados:
			report.espacios_actualizados.append(espacio)

	existing_reservas = {
		_reserva_recurrente_key(
			ImportRow(
				dia=d["dia_semana"],
				espacio=parent_espacio,
				hora_desde=str(r["hora_desde"]),
				hora_hasta=str(r["hora_hasta"]),
				etiqueta="",
				tipo_sesion="",
				arrendatario=r["arrendatario_nombre"],
			)
		)
		for r in frappe.get_all(
			"Reserva Espacio",
			filters={"tipo": "Alquiler externo", "modalidad_alquiler": "Recurrente"},
			fields=["name", "espacio", "hora_desde", "hora_hasta", "arrendatario_nombre"],
		)
		for parent_espacio in [r["espacio"]]
		for d in frappe.get_all(
			"Reserva Espacio Dia",
			filters={"parent": r["name"], "parenttype": "Reserva Espacio"},
			fields=["dia_semana"],
		)
	}

	# Reservas recurrentes ALQ
	for item in reservas:
		key = _reserva_recurrente_key(item)
		if key in existing_reservas:
			continue
		dup = frappe.db.exists(
			"Reserva Espacio",
			{
				"espacio": item.espacio,
				"tipo": "Alquiler externo",
				"modalidad_alquiler": "Recurrente",
				"hora_desde": item.hora_desde,
				"hora_hasta": item.hora_hasta,
				"arrendatario_nombre": item.arrendatario,
			},
		)
		if dup:
			parent = frappe.get_doc("Reserva Espacio", dup)
			dias = {d.dia_semana for d in (parent.get("dias_recurrencia") or [])}
			if item.dia not in dias:
				parent.append("dias_recurrencia", {"dia_semana": item.dia})
				parent.save(ignore_permissions=True)
			existing_reservas.add(key)
			continue
		if not frappe.db.get_value("Espacio", item.espacio, "alquilable"):
			frappe.db.set_value("Espacio", item.espacio, "alquilable", 1, update_modified=False)
		doc = frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": item.espacio,
				"tipo": "Alquiler externo",
				"modalidad_alquiler": "Recurrente",
				"estado": "Confirmada",
				"fecha_desde": "2026-01-01",
				"fecha_hasta": "2026-12-31",
				"fecha": "2026-01-01",
				"hora_desde": item.hora_desde,
				"hora_hasta": item.hora_hasta,
				"arrendatario_nombre": item.arrendatario,
				"motivo": item.etiqueta,
				"dias_recurrencia": [{"dia_semana": item.dia}],
			}
		)
		doc.insert(ignore_permissions=True)
		report.reservas_creadas += 1
		existing_reservas.add(key)

	existing_eventos = {
		_evento_club_recurrente_key(
			ImportRow(
				dia=d["dia_semana"],
				espacio=parent_espacio,
				hora_desde=str(r["hora_desde"]),
				hora_hasta=str(r["hora_hasta"]),
				etiqueta="",
				tipo_sesion="Evento club",
				motivo_evento=r["motivo"],
			)
		)
		for r in frappe.get_all(
			"Reserva Espacio",
			filters={"tipo": "Evento club", "recurrencia_semanal": 1, "estado": "Confirmada"},
			fields=["name", "espacio", "hora_desde", "hora_hasta", "motivo"],
		)
		for parent_espacio in [r["espacio"]]
		for d in frappe.get_all(
			"Reserva Espacio Dia",
			filters={"parent": r["name"], "parenttype": "Reserva Espacio"},
			fields=["dia_semana"],
		)
	}

	for item in eventos_club:
		key = _evento_club_recurrente_key(item)
		if key in existing_eventos:
			continue
		motivo = (item.motivo_evento or item.etiqueta or "").strip()
		dup = frappe.db.exists(
			"Reserva Espacio",
			{
				"espacio": item.espacio,
				"tipo": "Evento club",
				"recurrencia_semanal": 1,
				"estado": "Confirmada",
				"hora_desde": item.hora_desde,
				"hora_hasta": item.hora_hasta,
				"motivo": motivo,
			},
		)
		if dup:
			parent = frappe.get_doc("Reserva Espacio", dup)
			dias = {d.dia_semana for d in (parent.get("dias_recurrencia") or [])}
			if item.dia not in dias:
				parent.append("dias_recurrencia", {"dia_semana": item.dia})
				parent.save(ignore_permissions=True)
			existing_eventos.add(key)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Reserva Espacio",
				"espacio": item.espacio,
				"tipo": "Evento club",
				"recurrencia_semanal": 1,
				"estado": "Confirmada",
				"fecha_desde": "2026-01-01",
				"fecha_hasta": "2026-12-31",
				"fecha": "2026-01-01",
				"hora_desde": item.hora_desde,
				"hora_hasta": item.hora_hasta,
				"motivo": motivo,
				"dias_recurrencia": [{"dia_semana": item.dia}],
			}
		)
		doc.flags.skip_grid_overlap_check = True
		doc.insert(ignore_permissions=True)
		report.eventos_club_creados += 1
		existing_eventos.add(key)

	return {
		"horarios_creados": report.horarios_creados,
		"reservas_creadas": report.reservas_creadas,
		"eventos_club_creados": report.eventos_club_creados,
		"espacios_actualizados": report.espacios_actualizados,
		"omitidos": report.omitidos,
		"errores": report.errores,
	}


def default_horarios_csv_path() -> Path:
	return Path(frappe.get_app_path("club_management")) / "spaces" / "fixtures" / "horarios_lunes_viernes.csv"


def default_horarios_sabado_csv_path() -> Path:
	return Path(frappe.get_app_path("club_management")) / "spaces" / "fixtures" / "horarios_sabado.csv"


def import_horarios_sabado(path: str | Path | None = None) -> dict[str, Any]:
	"""Importa actividades fijas de sábado (reemplaza solo filas Sabado)."""
	csv_path = Path(path) if path else default_horarios_sabado_csv_path()
	return import_horarios_csv(
		csv_path,
		replace_weekdays=False,
		replace_days={"Sabado"},
	)