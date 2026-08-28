"""KPIs y agregaciones del dashboard Gestión de Actividades y Deportes."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import frappe
from frappe.utils import add_days, cint, flt, get_first_day, get_last_day, getdate, today

from club_management.activities.services.gestion_actividades_panel import (
	ACTIVIDAD_DOCTYPE,
	EQUIPO_DOCTYPE,
	GRUPO_DOCTYPE,
	INSCRIPCION_DOCTYPE,
)

LISTA_ESPERA_DOCTYPE = "Lista Espera Actividad"
ASISTENCIA_DOCTYPE = "Asistencia Sesion"
SOCIO_DOCTYPE = "Socio"

APTO_ALERTA_CANTIDAD = 50
OCUPACION_ALERTA_ROJA = 90.0

OCUPACION_SEGMENT_COLORS = (
	"#5e64ff",
	"#29cd42",
	"#f39c12",
	"#e74c3c",
	"#9b59b6",
	"#1abc9c",
	"#3498db",
	"#e67e22",
	"#8e44ad",
	"#16a085",
	"#d35400",
	"#c0392b",
	"#2c3e50",
	"#7f8c8d",
	"#27ae60",
	"#2980b9",
	"#f1c40f",
	"#e84393",
	"#00cec9",
	"#6c5ce7",
	"#fd79a8",
	"#00b894",
	"#636e72",
	"#a29bfe",
)


def _pct(numerator: float, denominator: float) -> float:
	if denominator <= 0:
		return 0.0
	return round(flt(numerator) / flt(denominator) * 100, 1)


def _semaforo_aptos(cantidad: int) -> str:
	if cantidad >= APTO_ALERTA_CANTIDAD:
		return "amarillo"
	return "verde"


def _semaforo_ocupacion(porcentaje: float) -> str:
	if porcentaje >= OCUPACION_ALERTA_ROJA:
		return "rojo"
	if porcentaje >= 75:
		return "amarillo"
	return "verde"


def count_inscripciones_activas(*, actividad: str | None = None) -> int:
	filters: dict[str, Any] = {"estado": "Activa"}
	if actividad:
		filters["actividad"] = actividad
	return frappe.db.count(INSCRIPCION_DOCTYPE, filters)


def _inscripciones_activas_rows(*, actividad: str | None = None) -> list[dict[str, Any]]:
	filters: dict[str, Any] = {"estado": "Activa"}
	if actividad:
		filters["actividad"] = actividad
	return frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=filters,
		fields=["name", "actividad", "grupo_actividad", "equipo_actividad", "socio"],
	)


def _capacity_nodes() -> list[dict[str, Any]]:
	"""Nodos hoja con capacidad: equipo > grupo (sin equipos con cupo) > actividad sin grupos."""
	nodes: list[dict[str, Any]] = []
	actividades = frappe.get_all(
		ACTIVIDAD_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "usa_grupos", "capacidad"],
	)
	grupos = frappe.get_all(
		GRUPO_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "actividad", "capacidad"],
	)
	equipos = frappe.get_all(
		EQUIPO_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo", "grupo_actividad", "capacidad"],
	)
	equipos_by_grupo: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for equipo in equipos:
		equipos_by_grupo[equipo["grupo_actividad"]].append(equipo)

	grupos_by_actividad: dict[str, list[dict[str, Any]]] = defaultdict(list)
	for grupo in grupos:
		grupos_by_actividad[grupo["actividad"]].append(grupo)

	for actividad in actividades:
		if not actividad["usa_grupos"]:
			cap = cint(actividad.get("capacidad"))
			if cap > 0:
				nodes.append(
					{
						"tipo": "actividad",
						"actividad": actividad["name"],
						"grupo_actividad": None,
						"equipo_actividad": None,
						"capacidad": cap,
						"label": actividad["name"],
					}
				)
			continue
		for grupo in grupos_by_actividad.get(actividad["name"], []):
			equipos_grupo = equipos_by_grupo.get(grupo["name"], [])
			equipos_con_cupo = [eq for eq in equipos_grupo if cint(eq.get("capacidad")) > 0]
			if equipos_con_cupo:
				for equipo in equipos_con_cupo:
					nodes.append(
						{
							"tipo": "equipo",
							"actividad": actividad["name"],
							"grupo_actividad": grupo["name"],
							"equipo_actividad": equipo["name"],
							"capacidad": cint(equipo.get("capacidad")),
							"label": f"{grupo['name']} / {equipo['name']}",
						}
					)
			elif cint(grupo.get("capacidad")) > 0:
				nodes.append(
					{
						"tipo": "grupo",
						"actividad": actividad["name"],
						"grupo_actividad": grupo["name"],
						"equipo_actividad": None,
						"capacidad": cint(grupo.get("capacidad")),
						"label": grupo["name"],
					}
				)
	return nodes


def _count_inscripciones_en_nodo(node: dict[str, Any]) -> int:
	filters: dict[str, Any] = {"estado": "Activa", "actividad": node["actividad"]}
	if node["equipo_actividad"]:
		filters["equipo_actividad"] = node["equipo_actividad"]
	elif node["grupo_actividad"]:
		filters["grupo_actividad"] = node["grupo_actividad"]
		filters["equipo_actividad"] = ["is", "not set"]
	else:
		filters["grupo_actividad"] = ["is", "not set"]
		filters["equipo_actividad"] = ["is", "not set"]
	return frappe.db.count(INSCRIPCION_DOCTYPE, filters)


def get_ocupacion_general_payload(*, actividad: str | None = None) -> dict[str, Any]:
	nodes = _capacity_nodes()
	if actividad:
		nodes = [node for node in nodes if node["actividad"] == actividad]
	capacidad_total = sum(node["capacidad"] for node in nodes)
	inscriptos_total = sum(_count_inscripciones_en_nodo(node) for node in nodes)
	porcentaje = _pct(inscriptos_total, capacidad_total)
	return {
		"inscriptos": inscriptos_total,
		"capacidad": capacidad_total,
		"porcentaje": porcentaje,
		"datos_completos": capacidad_total > 0,
		"semaforo": _semaforo_ocupacion(porcentaje) if capacidad_total > 0 else "verde",
	}


def get_actividad_mas_socios_payload(*, actividad: str | None = None) -> dict[str, Any]:
	rows = _inscripciones_activas_rows(actividad=actividad)
	by_actividad: dict[str, set[str]] = defaultdict(set)
	for row in rows:
		by_actividad[row["actividad"]].add(row["socio"])
	if not by_actividad:
		return {"actividad": None, "socios": 0}
	leader = max(by_actividad, key=lambda act: len(by_actividad[act]))
	return {"actividad": leader, "socios": len(by_actividad[leader])}


def get_crecimiento_actividad_payload(
	*, reference_date: str | date | None = None, actividad: str | None = None
) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	prev_last = first - timedelta(days=1)
	prev_first = get_first_day(prev_last)

	def _count_range(start: date, end: date) -> dict[str, int]:
		filters: dict[str, Any] = {
			"estado": "Activa",
			"fecha_inscripcion": ["between", [start, end]],
		}
		if actividad:
			filters["actividad"] = actividad
		rows = frappe.get_all(INSCRIPCION_DOCTYPE, filters=filters, fields=["actividad"])
		counts: dict[str, int] = defaultdict(int)
		for row in rows:
			counts[row["actividad"]] += 1
		return counts

	actual = _count_range(first, last)
	anterior = _count_range(prev_first, prev_last)
	leader = max(actual, key=actual.get) if actual else None
	delta = actual.get(leader, 0) - anterior.get(leader, 0) if leader else 0
	return {
		"actividad": leader,
		"altas_mes": actual.get(leader, 0) if leader else 0,
		"delta_mes_anterior": delta,
		"periodo": f"{first.strftime('%m/%Y')}",
	}


def _socios_con_inscripcion_activa() -> set[str]:
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": "Activa"},
		pluck="socio",
	)
	return set(rows)


def count_aptos_vencidos() -> int:
	ref = getdate(today())
	socios_deportistas = _socios_con_inscripcion_activa()
	if not socios_deportistas:
		return 0
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={
			"name": ["in", list(socios_deportistas)],
			"estado": ["!=", "Baja"],
		},
		fields=["name", "apto_medico_vencimiento"],
	)
	cantidad = 0
	for row in rows:
		vencimiento = row.get("apto_medico_vencimiento")
		if not vencimiento or getdate(vencimiento) < ref:
			cantidad += 1
	return cantidad


def get_aptos_vencidos_payload() -> dict[str, Any]:
	cantidad = count_aptos_vencidos()
	return {
		"cantidad": cantidad,
		"semaforo": _semaforo_aptos(cantidad),
	}


def _ocupacion_segment_color(index: int) -> str:
	return OCUPACION_SEGMENT_COLORS[index % len(OCUPACION_SEGMENT_COLORS)]


def get_ocupacion_por_deporte_payload(*, actividad: str | None = None) -> dict[str, Any]:
	rows = _inscripciones_activas_rows(actividad=actividad)
	by_actividad: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
	for row in rows:
		act = row["actividad"]
		segmento = row.get("grupo_actividad") or frappe._("Sin grupo")
		by_actividad[act][segmento] += 1

	actividades = sorted(
		by_actividad,
		key=lambda act: (-sum(by_actividad[act].values()), act),
	)
	segmentos_set: set[str] = set()
	for segments in by_actividad.values():
		segmentos_set.update(segments)
	segmentos = sorted(segmentos_set)
	color_by_segmento = {
		segmento: _ocupacion_segment_color(index) for index, segmento in enumerate(segmentos)
	}
	titulo_map: dict[str, str] = {}
	grupo_titulo_map: dict[str, str] = {}
	if actividades:
		for row in frappe.get_all(
			ACTIVIDAD_DOCTYPE,
			filters={"name": ["in", actividades]},
			fields=["name", "titulo"],
		):
			titulo_map[row["name"]] = row.get("titulo") or row["name"]
	if segmentos:
		grupo_ids = [segmento for segmento in segmentos if segmento != frappe._("Sin grupo")]
		if grupo_ids:
			for row in frappe.get_all(
				GRUPO_DOCTYPE,
				filters={"name": ["in", grupo_ids]},
				fields=["name", "titulo"],
			):
				grupo_titulo_map[row["name"]] = row.get("titulo") or row["name"]

	def _grupo_label(segmento: str) -> str:
		if segmento == frappe._("Sin grupo"):
			return segmento
		return grupo_titulo_map.get(segmento, segmento)

	composicion: dict[str, list[dict[str, Any]]] = {}
	for act in actividades:
		segmentos_actividad = []
		for segmento, cantidad in sorted(by_actividad[act].items()):
			if cantidad <= 0:
				continue
			segmentos_actividad.append(
				{
					"grupo": segmento,
					"grupo_label": _grupo_label(segmento),
					"inscriptos": cantidad,
					"color": color_by_segmento[segmento],
				}
			)
		composicion[act] = segmentos_actividad

	datasets = []
	for segmento in segmentos:
		datasets.append(
			{
				"name": _grupo_label(segmento),
				"values": [by_actividad[act].get(segmento, 0) for act in actividades],
				"color": color_by_segmento[segmento],
			}
		)

	return {
		"disponible": bool(actividades),
		"labels": actividades,
		"label_titulos": [titulo_map.get(act, act) for act in actividades],
		"datasets": datasets,
		"colors": [color_by_segmento[segmento] for segmento in segmentos],
		"composicion": composicion,
		"actividades_filtro": [
			{"name": act, "titulo": titulo_map.get(act, act)} for act in actividades
		],
	}


def get_lista_espera_top_payload(*, limit: int = 5) -> dict[str, Any]:
	if not frappe.db.table_exists(LISTA_ESPERA_DOCTYPE):
		return {"disponible": False, "filas": []}
	rows = frappe.get_all(
		LISTA_ESPERA_DOCTYPE,
		filters={"estado": "En espera"},
		fields=[
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
			"fecha_solicitud",
			"name",
		],
		order_by="fecha_solicitud asc",
	)
	grouped: dict[tuple[str, str | None, str | None], dict[str, Any]] = {}
	for row in rows:
		key = (row["actividad"], row.get("grupo_actividad"), row.get("equipo_actividad"))
		entry = grouped.setdefault(
			key,
			{
				"actividad": row["actividad"],
				"grupo_actividad": row.get("grupo_actividad"),
				"equipo_actividad": row.get("equipo_actividad"),
				"cantidad": 0,
				"fecha_mas_antigua": row.get("fecha_solicitud"),
			},
		)
		entry["cantidad"] += 1
		fecha = row.get("fecha_solicitud")
		if fecha and (not entry["fecha_mas_antigua"] or fecha < entry["fecha_mas_antigua"]):
			entry["fecha_mas_antigua"] = fecha

	filas = sorted(grouped.values(), key=lambda item: (-item["cantidad"], item["fecha_mas_antigua"] or ""))
	return {"disponible": True, "filas": filas[:limit]}


def get_asistencia_semanal_payload(
	*, reference_date: str | date | None = None, actividad: str | None = None, semanas: int = 4
) -> dict[str, Any]:
	if not frappe.db.table_exists(ASISTENCIA_DOCTYPE):
		return {"disponible": False, "semanas": [], "series": []}
	ref = getdate(reference_date or today())
	start = add_days(ref, -7 * semanas)
	filters: dict[str, Any] = {"fecha": [">=", start]}
	if actividad:
		filters["actividad"] = actividad
	rows = frappe.get_all(
		ASISTENCIA_DOCTYPE,
		filters=filters,
		fields=["fecha", "actividad", "inscriptos", "presentes"],
		order_by="fecha asc",
	)
	if not rows:
		return {"disponible": False, "semanas": [], "series": []}

	week_labels: list[str] = []
	week_starts: list[date] = []
	cursor = start
	while cursor <= ref:
		week_end = min(add_days(cursor, 6), ref)
		week_labels.append(f"{cursor.strftime('%d/%m')}")
		week_starts.append(cursor)
		cursor = add_days(cursor, 7)

	by_act_week: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
	for row in rows:
		fecha = getdate(row["fecha"])
		inscriptos = cint(row.get("inscriptos"))
		if inscriptos <= 0:
			continue
		week_index = min((fecha - start).days // 7, len(week_starts) - 1)
		pct = flt(row.get("presentes")) / flt(inscriptos) * 100
		by_act_week[row["actividad"]][week_index].append(pct)

	series = []
	for act, weeks_data in sorted(by_act_week.items()):
		values = []
		for idx in range(len(week_starts)):
			points = weeks_data.get(idx, [])
			values.append(round(sum(points) / len(points), 1) if points else 0)
		series.append({"actividad": act, "values": values})

	return {"disponible": bool(series), "semanas": week_labels, "series": series}


def get_infraestructura_payload() -> dict[str, Any]:
	"""Enlace al dashboard de ocupación de espacios."""
	return {
		"disponible": True,
		"mensaje": frappe._("Ver ocupación diaria de espacios (planilla 08:00–04:00)"),
		"workspace": "Espacios",
		"ruta": "/desk/ocupacion-espacios",
	}


def get_actividades_opciones() -> list[dict[str, str]]:
	"""Opciones ligeras para el filtro del dashboard (sin catálogo completo)."""
	return frappe.get_all(
		ACTIVIDAD_DOCTYPE,
		filters={"habilitada": 1},
		fields=["name", "titulo"],
		order_by="titulo asc, name asc",
	)


def get_dashboard_payload(
	*,
	reference_date: str | date | None = None,
	actividad: str | None = None,
) -> dict[str, Any]:
	ref = reference_date or today()
	crecimiento = get_crecimiento_actividad_payload(reference_date=ref, actividad=actividad)
	mas_socios = get_actividad_mas_socios_payload(actividad=actividad)
	mas_socios_filters: list[list[str]] = [
		["Inscripcion Actividad", "estado", "=", "Activa"],
	]
	if mas_socios.get("actividad"):
		mas_socios_filters.append(["Inscripcion Actividad", "actividad", "=", mas_socios["actividad"]])
	return {
		"kpis": {
			"inscripciones_activas": count_inscripciones_activas(actividad=actividad),
			"crecimiento": crecimiento,
			"mas_socios": mas_socios,
		},
		"actividades_opciones": get_actividades_opciones(),
		"ocupacion_por_deporte": get_ocupacion_por_deporte_payload(actividad=actividad),
		"lista_espera": get_lista_espera_top_payload(),
		"asistencia": get_asistencia_semanal_payload(reference_date=ref, actividad=actividad),
		"infraestructura": get_infraestructura_payload(),
		"filtros": {
			"actividad": actividad,
			"reference_date": str(getdate(ref)),
			"sede_disponible": False,
		},
		"ver_mas": {
			"inscripciones_doctype": INSCRIPCION_DOCTYPE,
			"inscripciones_filters": [["Inscripcion Actividad", "estado", "=", "Activa"]],
			"mas_socios_doctype": INSCRIPCION_DOCTYPE,
			"mas_socios_filters": mas_socios_filters,
			"lista_espera_doctype": LISTA_ESPERA_DOCTYPE,
			"lista_espera_filters": [["Lista Espera Actividad", "estado", "=", "En espera"]],
			"asistencia_doctype": ASISTENCIA_DOCTYPE,
			"asistencia_filters": [],
		},
	}
