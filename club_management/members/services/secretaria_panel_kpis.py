"""KPIs del panel Desk Secretaría (socios y recaudación mensual)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate, today

from club_management.members.services.recibo_pago import format_monto_ar

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_item_arancel_inscripcion,
)
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_LEGACY_ITEM_CODE
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	get_club_settings,
)
from club_management.members.services.cobranza_periodica import (
	_campo_periodo_cobro,
	format_periodo_cobro,
)
from club_management.members.services.concepto_informe_label import (
	agrupacion_tipo_concepto,
	etiqueta_concepto_informe_desde_linea_si,
)
from club_management.members.services.mora_al_cobro import (
	MORA_SUFFIX,
	fechas_vencimiento_periodo,
)

SOCIO_DOCTYPE = "Socio"
ESTADOS_EXCLUIDOS_TOTAL = frozenset({"Baja"})
CATEGORIA_NO_SOCIO = "No Socio"
SALES_INVOICE_ITEM_DOCTYPE = "Sales Invoice Item"
PAYMENT_ENTRY_DOCTYPE = "Payment Entry"
PAYMENT_ENTRY_REFERENCE_DOCTYPE = "Payment Entry Reference"
RECARGO_SUFFIX = "-REC"

CATEGORIAS_GRAFICO = ("Activo", "Menor", "Adherente", "Jubilado", "Vitalicio")
CATEGORIAS_CUOTA_INFORME = CATEGORIAS_GRAFICO
COBRABILIDAD_VISTAS = (
	("total", "Total"),
	("cuota", "Cuotas sociales"),
	("arancel", "Aranceles"),
	("cto_comp", "CTO COMP"),
	("federativa", "Federativas"),
	("otro", "Otros conceptos"),
)
TRAMOS_MORA = (
	("1", "1 mes"),
	("2", "2 meses"),
	("3", "3 meses"),
	("4_mas", "+4 meses"),
)
TRAMOS_MORA_1_3 = frozenset({"1", "2", "3"})
CATEGORIAS_HERMANO = frozenset({"2° Hermano", "3° Hermano"})
_EDAD_MAYORIA = 18

from club_management.members.services.modos_pago_desk import agrupar_modo_pago_chart


def _last_day_previous_month(reference: date) -> date:
	first_current = reference.replace(day=1)
	return first_current.replace(day=1) - timedelta(days=1)


def _pct(recaudado: float, emitido: float) -> float:
	if emitido <= 0:
		return 0.0
	return round(flt(recaudado) / flt(emitido) * 100, 1)


def count_socios_total(*, as_of: date | None = None) -> int:
	filters: dict[str, Any] = {
		"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)],
		"categoria": ["!=", CATEGORIA_NO_SOCIO],
	}
	if as_of:
		filters["creation"] = ["<=", as_of]
	return frappe.db.count(SOCIO_DOCTYPE, filters)


def get_morosos_deuda_total() -> float:
	"""Suma de `saldo_deuda` de socios con estado Moroso."""
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": "Moroso"},
		pluck="saldo_deuda",
	)
	return sum(flt(value) for value in rows)


def _es_menor_edad(fecha_nacimiento: str | date | None, *, as_of: date) -> bool:
	if not fecha_nacimiento:
		return False
	nac = getdate(fecha_nacimiento)
	edad = as_of.year - nac.year - ((as_of.month, as_of.day) < (nac.month, nac.day))
	return edad < _EDAD_MAYORIA


def _categoria_grafico_socio(
	categoria: str,
	fecha_nacimiento: str | date | None,
	*,
	as_of: date,
) -> str | None:
	if categoria in CATEGORIAS_HERMANO:
		return "Menor" if _es_menor_edad(fecha_nacimiento, as_of=as_of) else "Activo"
	if categoria in CATEGORIAS_GRAFICO:
		return categoria
	return None


def get_socios_por_categoria(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Total socios activos (no Baja) desglosado por categoría del gráfico."""
	as_of = getdate(reference_date or today())
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)]},
		fields=["categoria", "fecha_nacimiento"],
	)
	categorias = {categoria: 0 for categoria in CATEGORIAS_GRAFICO}
	for row in rows:
		bucket = _categoria_grafico_socio(
			row.categoria or "",
			row.fecha_nacimiento,
			as_of=as_of,
		)
		if bucket:
			categorias[bucket] += 1
	total = sum(categorias.values())
	return {"total": total, **categorias}


def get_socios_por_segmento(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Compatibilidad: delega en get_socios_por_categoria."""
	return get_socios_por_categoria(reference_date=reference_date)


def count_altas_bajas_mes(*, reference_date: str | date | None = None) -> dict[str, int]:
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	altas = frappe.db.count(
		SOCIO_DOCTYPE,
		{
			"fecha_alta": ["between", [first, last]],
			"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)],
			"categoria": ["!=", CATEGORIA_NO_SOCIO],
		},
	)
	bajas = frappe.db.count(
		SOCIO_DOCTYPE,
		{
			"estado": "Baja",
			"categoria": ["!=", CATEGORIA_NO_SOCIO],
			"ultimo_cambio_estado_en": ["between", [f"{first} 00:00:00", f"{last} 23:59:59"]],
		},
	)
	return {"altas": altas, "bajas": bajas}


def _periodo_mes_base(periodo: str | None) -> str:
	raw = (periodo or "").strip()
	for suffix in (MORA_SUFFIX, RECARGO_SUFFIX):
		if raw.endswith(suffix):
			return raw[: -len(suffix)]
	return raw


def contar_meses_vencidos(
	periodos: list[str],
	*,
	as_of: date,
	dia_primer_vencimiento: int = 10,
	dia_segundo_vencimiento: str | None = "20",
) -> int:
	"""Meses distintos impagos cuyo 2.º vencimiento ya pasó a `as_of`."""
	vencidos: set[str] = set()
	for periodo in periodos:
		base = _periodo_mes_base(periodo)
		fechas = fechas_vencimiento_periodo(
			base,
			dia_primer_vencimiento=dia_primer_vencimiento,
			dia_segundo_vencimiento=dia_segundo_vencimiento,
		)
		if fechas and as_of > fechas[1]:
			vencidos.add(base)
	return len(vencidos)


def tramo_mora_por_meses(meses: int) -> str | None:
	if meses < 1:
		return None
	return "4_mas" if meses >= 4 else str(meses)


def get_mora_1_3_meses_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Socios con 1 a 3 meses vencidos impagos y monto total de su deuda."""
	tramos = get_mora_clasificacion_payload(reference_date=reference_date)["tramos"]
	seleccion = [t for t in tramos if t["key"] in TRAMOS_MORA_1_3]
	monto = round(sum(flt(t["monto"]) for t in seleccion), 2)
	return {
		"cantidad": sum(int(t["cantidad"]) for t in seleccion),
		"monto": monto,
		"monto_label": format_monto_ar(monto),
	}


def get_mora_clasificacion_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Clasifica socios por cantidad de meses vencidos impagos: 1, 2, 3, +4."""
	as_of = getdate(reference_date or today())
	buckets = {
		key: {"key": key, "label": label, "cantidad": 0, "monto": 0.0} for key, label in TRAMOS_MORA
	}
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE) if erpnext_cobranza_disponible() else None
	campo_periodo = _campo_periodo_cobro() if campo_socio else None
	if campo_socio and campo_periodo:
		settings = get_club_settings()
		dia_v1 = int(settings.dia_primer_vencimiento or 10)
		dia_v2 = settings.dia_segundo_vencimiento or "20"
		socios = {
			row.name: flt(row.saldo_deuda)
			for row in frappe.get_all(
				SOCIO_DOCTYPE,
				filters={"estado": ["not in", list(ESTADOS_EXCLUIDOS_TOTAL)]},
				fields=["name", "saldo_deuda"],
			)
		}
		periodos_por_socio: dict[str, list[str]] = {}
		for row in frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={
				campo_socio: ["is", "set"],
				"docstatus": 1,
				"outstanding_amount": [">", 0],
			},
			fields=[campo_socio, campo_periodo],
		):
			socio = row.get(campo_socio)
			if socio in socios:
				periodos_por_socio.setdefault(socio, []).append(row.get(campo_periodo) or "")
		for socio, periodos in periodos_por_socio.items():
			key = tramo_mora_por_meses(
				contar_meses_vencidos(
					periodos,
					as_of=as_of,
					dia_primer_vencimiento=dia_v1,
					dia_segundo_vencimiento=dia_v2,
				)
			)
			if not key:
				continue
			buckets[key]["cantidad"] += 1
			buckets[key]["monto"] += socios[socio]

	tramos: list[dict[str, Any]] = []
	for key, _label in TRAMOS_MORA:
		bucket = buckets[key]
		tramos.append(
			{
				**bucket,
				"monto": round(flt(bucket["monto"]), 2),
				"monto_label": format_monto_ar(bucket["monto"]),
			}
		)
	return {"tramos": tramos}


def _bajas_inscripcion_en_rango(desde: date, hasta: date) -> list[str]:
	"""Inscripciones cuyo `estado` pasó a Baja dentro del rango (historial de versiones)."""
	rows = frappe.get_all(
		"Version",
		filters={
			"ref_doctype": INSCRIPCION_DOCTYPE,
			"creation": ["between", [f"{desde} 00:00:00", f"{hasta} 23:59:59"]],
			"data": ["like", '%"estado"%'],
		},
		fields=["docname", "data"],
	)
	bajas: list[str] = []
	for row in rows:
		try:
			changed = json.loads(row.data or "{}").get("changed") or []
		except ValueError:
			continue
		if any(len(c) >= 3 and c[0] == "estado" and c[2] == "Baja" for c in changed):
			bajas.append(row.docname)
	return bajas


def get_actividades_movimientos(
	*,
	reference_date: str | date | None = None,
	dias: int = 30,
	limit: int | None = 3,
) -> dict[str, Any]:
	"""Actividades con más altas + bajas de inscripciones en los últimos `dias` días."""
	hasta = getdate(reference_date or today())
	desde = hasta - timedelta(days=dias - 1)
	stats: dict[str, dict[str, Any]] = {}

	def _row(actividad: str) -> dict[str, Any]:
		return stats.setdefault(
			actividad, {"actividad": actividad, "altas": 0, "bajas": 0, "total": 0}
		)

	for actividad in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"fecha_inscripcion": ["between", [desde, hasta]]},
		pluck="actividad",
	):
		if actividad:
			_row(actividad)["altas"] += 1

	bajas = _bajas_inscripcion_en_rango(desde, hasta)
	if bajas:
		actividad_por_inscripcion = dict(
			frappe.get_all(
				INSCRIPCION_DOCTYPE,
				filters={"name": ["in", sorted(set(bajas))]},
				fields=["name", "actividad"],
				as_list=True,
			)
		)
		for inscripcion in bajas:
			actividad = actividad_por_inscripcion.get(inscripcion)
			if actividad:
				_row(actividad)["bajas"] += 1

	for row in stats.values():
		row["total"] = row["altas"] + row["bajas"]
	ordenadas = sorted(
		(row for row in stats.values() if row["total"] > 0),
		key=lambda r: (-r["total"], -r["altas"], r["actividad"]),
	)
	if limit is not None:
		ordenadas = ordenadas[:limit]
	return {"desde": str(desde), "hasta": str(hasta), "dias": dias, "actividades": ordenadas}


def _finalize_tendencia_dias(dias: list[dict[str, Any]]) -> dict[str, Any]:
	"""Acumula la serie y devuelve el resumen del mes (emitido, recaudado, %, saldo)."""
	emitido_acum = 0.0
	recaudado_acum = 0.0
	for row in dias:
		emitido_acum += flt(row.pop("emitido_dia", 0))
		recaudado_acum += flt(row.pop("recaudado_dia", 0))
		row["recaudado"] = round(recaudado_acum, 2)
		row["deuda"] = round(max(emitido_acum - recaudado_acum, 0), 2)
	emitido = round(emitido_acum, 2)
	recaudado = round(recaudado_acum, 2)
	saldo = round(max(emitido_acum - recaudado_acum, 0), 2)
	return {
		"emitido": emitido,
		"recaudado": recaudado,
		"porcentaje": _pct(recaudado, emitido),
		"saldo": saldo,
		"emitido_label": format_monto_ar(emitido),
		"recaudado_label": format_monto_ar(recaudado),
		"saldo_label": format_monto_ar(saldo),
	}


def _tendencia_hasta_dia(first: date, last: date) -> int:
	hoy = getdate(today())
	if first <= hoy <= last:
		return hoy.day
	return last.day


def _dia_en_mes_periodo(
	posting_date: str | date | None,
	*,
	period_first: date,
	period_last: date,
	fallback_day: int,
) -> int | None:
	"""Mapea una fecha contable al día 1…N del mes del período visualizado."""
	if not posting_date:
		return min(max(int(fallback_day), 1), period_last.day)
	posting = getdate(posting_date)
	if period_first <= posting <= period_last:
		return posting.day
	if posting < period_first:
		return min(max(int(fallback_day), 1), period_last.day)
	return period_last.day


def _clasificar_linea_vista(
	item_code: str,
	description: str | None,
	*,
	cuota_items: set[str],
	arancel_map: dict[str, str],
	categoria_socio: str | None = None,
) -> str:
	"""Vista de cobrabilidad/tendencia: cuota | arancel | cto_comp | federativa | otro."""
	etiqueta = etiqueta_concepto_informe_desde_linea_si(
		item_code,
		description,
		categoria_socio=categoria_socio,
	)
	tipo = agrupacion_tipo_concepto(etiqueta)
	es_arancel = bool(arancel_map.get(item_code)) or tipo == "Arancel"
	es_cuota = (tipo == "Cuota" or item_code in cuota_items) and not es_arancel
	if es_cuota:
		return "cuota"
	if es_arancel:
		return "arancel"
	if tipo == "CTO COMP":
		return "cto_comp"
	if tipo == "Federativa":
		return "federativa"
	return "otro"


def _linea_entra_en_vista(vista: str, linea_vista: str) -> bool:
	vista_norm = (vista or "total").strip().lower()
	if vista_norm in ("", "total"):
		return True
	return linea_vista == vista_norm


def get_recaudacion_tendencia_payload(
	*,
	reference_date: str | date | None = None,
	vista: str = "total",
) -> dict[str, Any]:
	"""Serie diaria acumulada deuda vs recaudado, filtrable por vista (como cobrabilidad)."""
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	periodo = format_periodo_cobro(ref)
	vista_norm = (vista or "total").strip().lower() or "total"
	vistas = [{"value": value, "label": label} for value, label in COBRABILIDAD_VISTAS]
	dias: list[dict[str, Any]] = [
		{"dia": day, "label": str(day), "emitido_dia": 0.0, "recaudado_dia": 0.0}
		for day in range(1, last.day + 1)
	]
	by_day = {row["dia"]: row for row in dias}
	payload: dict[str, Any] = {
		"periodo": periodo,
		"reference_date": str(first),
		"dias": dias,
		"disponible": False,
		"vista": vista_norm,
		"vistas": vistas,
		"hasta_dia": _tendencia_hasta_dia(first, last),
	}
	if not erpnext_cobranza_disponible():
		return {**payload, "resumen": _finalize_tendencia_dias(dias)}

	campo_periodo = _campo_periodo_cobro()
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_periodo or not campo_socio:
		return {**payload, "resumen": _finalize_tendencia_dias(dias)}

	settings = get_club_settings()
	cuota_items = _cuota_item_codes(settings)
	arancel_map = _arancel_item_actividad_map()
	emit_day = int(settings.dia_generacion_deuda or 1)
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1},
		fields=["name", "posting_date", "grand_total", campo_socio],
	)
	if not invoices:
		resumen = _finalize_tendencia_dias(dias)
		return {**payload, "dias": dias, "disponible": True, "resumen": resumen}

	socio_ids = {row.get(campo_socio) for row in invoices if row.get(campo_socio)}
	socio_categorias: dict[str, str | None] = {}
	if socio_ids:
		for socio in frappe.get_all(
			SOCIO_DOCTYPE,
			filters={"name": ["in", list(socio_ids)]},
			fields=["name", "categoria"],
		):
			socio_categorias[socio.name] = socio.categoria

	lines_by_parent = _invoice_lines_by_parent([row.name for row in invoices])
	invoice_by_name = {row.name: row for row in invoices}

	for invoice in invoices:
		day = _dia_en_mes_periodo(
			invoice.posting_date,
			period_first=first,
			period_last=last,
			fallback_day=emit_day,
		)
		if day is None:
			continue
		categoria_socio = socio_categorias.get(invoice.get(campo_socio))
		for line in lines_by_parent.get(invoice.name, []):
			item_code = line.get("item_code") or ""
			linea_vista = _clasificar_linea_vista(
				item_code,
				line.get("description"),
				cuota_items=cuota_items,
				arancel_map=arancel_map,
				categoria_socio=categoria_socio,
			)
			if not _linea_entra_en_vista(vista_norm, linea_vista):
				continue
			by_day[day]["emitido_dia"] += flt(line.get("amount"))

	pe_names = frappe.get_all(
		PAYMENT_ENTRY_REFERENCE_DOCTYPE,
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", list(invoice_by_name)],
			"parenttype": PAYMENT_ENTRY_DOCTYPE,
		},
		fields=["parent", "reference_name", "allocated_amount"],
	)
	if pe_names:
		parent_names = sorted({row.parent for row in pe_names})
		pe_by_name = {
			row.name: row
			for row in frappe.get_all(
				PAYMENT_ENTRY_DOCTYPE,
				filters={
					"name": ["in", parent_names],
					"docstatus": 1,
				},
				fields=["name", "posting_date"],
			)
		}
		for ref_row in pe_names:
			pe = pe_by_name.get(ref_row.parent)
			invoice = invoice_by_name.get(ref_row.reference_name)
			if not pe or not invoice:
				continue
			grand_total = flt(invoice.grand_total)
			if grand_total <= 0:
				continue
			categoria_socio = socio_categorias.get(invoice.get(campo_socio))
			relevant_total = sum(
				flt(line.get("amount"))
				for line in lines_by_parent.get(invoice.name, [])
				if _linea_entra_en_vista(
					vista_norm,
					_clasificar_linea_vista(
						line.get("item_code") or "",
						line.get("description"),
						cuota_items=cuota_items,
						arancel_map=arancel_map,
						categoria_socio=categoria_socio,
					),
				)
			)
			if relevant_total <= 0:
				continue
			paid = flt(ref_row.allocated_amount) * (relevant_total / grand_total)
			day = _dia_en_mes_periodo(
				pe.posting_date,
				period_first=first,
				period_last=last,
				fallback_day=emit_day,
			)
			if day is None:
				continue
			by_day[day]["recaudado_dia"] += paid

	resumen = _finalize_tendencia_dias(dias)
	return {**payload, "dias": dias, "disponible": True, "resumen": resumen}


def _agrupar_modo_pago(mode: str | None) -> str:
	return agrupar_modo_pago_chart(mode)


def get_medios_pago_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Distribución de cobros del mes por medio de pago agrupado."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	empty = {
		"periodo": periodo,
		"disponible": False,
		"efectivo": 0.0,
		"tarjeta": 0.0,
		"transferencia": 0.0,
		"otro": 0.0,
	}
	if not erpnext_cobranza_disponible():
		return empty
	if not frappe.db.exists("DocType", PAYMENT_ENTRY_DOCTYPE):
		return empty

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return empty

	first = get_first_day(ref)
	last = get_last_day(ref)
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_socio: ["is", "set"], "docstatus": 1},
		pluck="name",
	)
	if not invoices:
		return {**empty, "disponible": True}

	pe_names = frappe.get_all(
		PAYMENT_ENTRY_REFERENCE_DOCTYPE,
		filters={
			"reference_doctype": SALES_INVOICE_DOCTYPE,
			"reference_name": ["in", invoices],
			"parenttype": PAYMENT_ENTRY_DOCTYPE,
		},
		pluck="parent",
		distinct=True,
	)
	if not pe_names:
		return {**empty, "disponible": True}

	totals = {"efectivo": 0.0, "tarjeta": 0.0, "transferencia": 0.0, "otro": 0.0}
	for row in frappe.get_all(
		PAYMENT_ENTRY_DOCTYPE,
		filters={
			"name": ["in", pe_names],
			"docstatus": 1,
			"posting_date": ["between", [first, last]],
		},
		fields=["mode_of_payment", "paid_amount"],
	):
		key = _agrupar_modo_pago(row.mode_of_payment)
		totals[key] += flt(row.paid_amount)

	return {"periodo": periodo, "disponible": True, **totals}


def get_socio_metricas_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	segmentos = get_socios_por_categoria(reference_date=ref)
	total = segmentos["total"]
	total_mes_anterior = count_socios_total(as_of=_last_day_previous_month(ref))
	delta = total - total_mes_anterior
	morosos = frappe.db.count(SOCIO_DOCTYPE, {"estado": "Moroso"})
	morosos_deuda = get_morosos_deuda_total()
	mora_clasificacion = get_mora_clasificacion_payload()
	tramos_1_3 = [t for t in mora_clasificacion["tramos"] if t["key"] in TRAMOS_MORA_1_3]
	monto_1_3 = round(sum(flt(t["monto"]) for t in tramos_1_3), 2)
	mora_1_3 = {
		"cantidad": sum(int(t["cantidad"]) for t in tramos_1_3),
		"monto": monto_1_3,
		"monto_label": format_monto_ar(monto_1_3),
	}
	return {
		"total": total,
		"segmentos": segmentos,
		"total_mes_anterior": total_mes_anterior,
		"delta_mes": delta,
		"altas_bajas": count_altas_bajas_mes(reference_date=ref),
		"actividades_movimientos": get_actividades_movimientos(reference_date=ref),
		"morosos": morosos,
		"morosos_deuda": morosos_deuda,
		"morosos_deuda_label": format_monto_ar(morosos_deuda),
		"mora_1_3": {
			"cantidad": mora_1_3["cantidad"],
			"monto": mora_1_3["monto"],
			"monto_label": mora_1_3["monto_label"],
		},
		"mora_clasificacion": mora_clasificacion,
	}


def _cuota_item_codes(settings: frappe._dict) -> set[str]:
	codes = {settings.item_cuota_social, CUOTA_SOCIAL_LEGACY_ITEM_CODE}
	for row in settings.cuotas_categoria or []:
		if row.item:
			codes.add(row.item)
	return {code for code in codes if code}


def _arancel_item_actividad_map() -> dict[str, str]:
	mapping: dict[str, str] = {}
	if not frappe.db.table_exists(INSCRIPCION_DOCTYPE):
		return mapping
	for row in frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": "Activa"},
		fields=["name", "actividad"],
	):
		item_code = resolve_item_arancel_inscripcion(row.name)
		if item_code and row.actividad:
			mapping[item_code] = row.actividad
	return mapping


def _invoice_lines_by_parent(invoice_names: list[str]) -> dict[str, list[dict[str, Any]]]:
	if not invoice_names:
		return {}
	rows = frappe.get_all(
		SALES_INVOICE_ITEM_DOCTYPE,
		filters={"parent": ["in", invoice_names], "docstatus": ["<", 2]},
		fields=["parent", "item_code", "description", "amount"],
	)
	grouped: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def _cuotas_sociales_kpi_payload(*, emitido: float, recaudado: float) -> dict[str, Any]:
	pendiente = max(flt(emitido) - flt(recaudado), 0.0)
	return {
		"emitido": emitido,
		"recaudado": recaudado,
		"saldo_por_cobrar": pendiente,
		"emitido_label": format_monto_ar(emitido),
		"recaudado_label": format_monto_ar(recaudado),
		"saldo_por_cobrar_label": format_monto_ar(pendiente),
		"porcentaje": _pct(recaudado, emitido),
	}


def _kpi_slice_payload(*, emitido: float, recaudado: float) -> dict[str, Any]:
	return _cuotas_sociales_kpi_payload(emitido=emitido, recaudado=recaudado)


def _categoria_cuota_desde_etiqueta(etiqueta: str) -> str:
	prefix = "Cuota Social "
	if etiqueta.startswith(prefix):
		categoria = etiqueta[len(prefix) :].strip()
		if categoria in CATEGORIAS_CUOTA_INFORME:
			return categoria
	return "General"


def _accumulate_totals(
	buckets: dict[str, dict[str, float]],
	key: str,
	*,
	emitido: float,
	recaudado: float,
) -> None:
	row = buckets.setdefault(key, {"emitido": 0.0, "recaudado": 0.0})
	row["emitido"] += emitido
	row["recaudado"] += recaudado


def _rows_from_buckets(buckets: dict[str, dict[str, float]], *, label_key: str) -> list[dict[str, Any]]:
	rows: list[dict[str, Any]] = []
	for key in sorted(buckets):
		emitido = buckets[key]["emitido"]
		recaudado = buckets[key]["recaudado"]
		rows.append(
			{
				label_key: key,
				**_kpi_slice_payload(emitido=emitido, recaudado=recaudado),
			}
		)
	return rows


def _cobrabilidad_vistas_payload() -> list[dict[str, str]]:
	return [{"value": value, "label": label} for value, label in COBRABILIDAD_VISTAS]


def _empty_recaudacion_payload(periodo: str) -> dict[str, Any]:
	empty_kpi = _kpi_slice_payload(emitido=0.0, recaudado=0.0)
	return {
		"periodo": periodo,
		"total": dict(empty_kpi),
		"cuotas_sociales": {**empty_kpi, "por_categoria": []},
		"aranceles": {**empty_kpi, "por_actividad": []},
		"cto_comp": {**empty_kpi, "por_concepto": []},
		"federativa": {**empty_kpi, "por_concepto": []},
		"otros": {**empty_kpi, "por_concepto": []},
		"cobrabilidad_vistas": _cobrabilidad_vistas_payload(),
		"disponible": False,
	}


def get_recaudacion_mes_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Recaudación del período MM/YYYY con desglose para la card de cobrabilidad."""
	ref = getdate(reference_date or today())
	periodo = format_periodo_cobro(ref)
	empty = _empty_recaudacion_payload(periodo)
	if not erpnext_cobranza_disponible():
		return empty

	campo_periodo = _campo_periodo_cobro()
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_periodo or not campo_socio:
		return empty

	settings = get_club_settings()
	cuota_items = _cuota_item_codes(settings)
	arancel_map = _arancel_item_actividad_map()

	invoice_fields = ["name", "grand_total", "outstanding_amount", campo_socio]
	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={campo_periodo: periodo, "docstatus": 1},
		fields=invoice_fields,
	)
	if not invoices:
		return {**empty, "disponible": True}

	socio_ids = {row.get(campo_socio) for row in invoices if row.get(campo_socio)}
	socio_categorias: dict[str, str | None] = {}
	if socio_ids:
		for socio in frappe.get_all(
			SOCIO_DOCTYPE,
			filters={"name": ["in", list(socio_ids)]},
			fields=["name", "categoria"],
		):
			socio_categorias[socio.name] = socio.categoria

	lines_by_parent = _invoice_lines_by_parent([row.name for row in invoices])

	total_emitido = 0.0
	total_recaudado = 0.0
	cuota_emitido = 0.0
	cuota_recaudado = 0.0
	arancel_emitido = 0.0
	arancel_recaudado = 0.0
	otros_emitido = 0.0
	otros_recaudado = 0.0
	cto_comp_emitido = 0.0
	cto_comp_recaudado = 0.0
	federativa_emitido = 0.0
	federativa_recaudado = 0.0
	categoria_buckets: dict[str, dict[str, float]] = {}
	actividad_buckets: dict[str, dict[str, float]] = {}
	cto_comp_buckets: dict[str, dict[str, float]] = {}
	federativa_buckets: dict[str, dict[str, float]] = {}
	otros_buckets: dict[str, dict[str, float]] = {}

	for invoice in invoices:
		grand_total = flt(invoice.grand_total)
		if grand_total <= 0:
			continue
		paid_ratio = max(flt(invoice.grand_total) - flt(invoice.outstanding_amount), 0) / grand_total
		categoria_socio = socio_categorias.get(invoice.get(campo_socio))
		for line in lines_by_parent.get(invoice.name, []):
			amount = flt(line.amount)
			if amount <= 0:
				continue
			paid = amount * paid_ratio
			item_code = line.item_code or ""
			etiqueta = etiqueta_concepto_informe_desde_linea_si(
				item_code,
				line.description,
				categoria_socio=categoria_socio,
			)
			tipo = agrupacion_tipo_concepto(etiqueta)
			actividad_arancel = arancel_map.get(item_code)
			es_arancel = bool(actividad_arancel) or tipo == "Arancel"
			es_cuota = (tipo == "Cuota" or item_code in cuota_items) and not es_arancel

			total_emitido += amount
			total_recaudado += paid

			if es_cuota:
				cuota_emitido += amount
				cuota_recaudado += paid
				categoria = _categoria_cuota_desde_etiqueta(etiqueta)
				_accumulate_totals(
					categoria_buckets,
					categoria,
					emitido=amount,
					recaudado=paid,
				)
				continue

			if es_arancel:
				arancel_emitido += amount
				arancel_recaudado += paid
				actividad = actividad_arancel or etiqueta
				_accumulate_totals(
					actividad_buckets,
					actividad,
					emitido=amount,
					recaudado=paid,
				)
				continue

			if tipo == "CTO COMP":
				cto_comp_emitido += amount
				cto_comp_recaudado += paid
				_accumulate_totals(cto_comp_buckets, etiqueta, emitido=amount, recaudado=paid)
				continue
			if tipo == "Federativa":
				federativa_emitido += amount
				federativa_recaudado += paid
				_accumulate_totals(federativa_buckets, etiqueta, emitido=amount, recaudado=paid)
				continue

			otros_emitido += amount
			otros_recaudado += paid
			_accumulate_totals(otros_buckets, etiqueta, emitido=amount, recaudado=paid)

	def _concept_rows(buckets: dict[str, dict[str, float]], *, tipo: str) -> list[dict[str, Any]]:
		rows: list[dict[str, Any]] = []
		for concepto in sorted(buckets):
			emitido = buckets[concepto]["emitido"]
			recaudado = buckets[concepto]["recaudado"]
			rows.append(
				{
					"tipo": tipo,
					"concepto": concepto,
					**_kpi_slice_payload(emitido=emitido, recaudado=recaudado),
				}
			)
		return rows

	return {
		"periodo": periodo,
		"disponible": True,
		"total": _kpi_slice_payload(emitido=total_emitido, recaudado=total_recaudado),
		"cuotas_sociales": {
			**_kpi_slice_payload(emitido=cuota_emitido, recaudado=cuota_recaudado),
			"por_categoria": _rows_from_buckets(categoria_buckets, label_key="categoria"),
		},
		"aranceles": {
			**_kpi_slice_payload(emitido=arancel_emitido, recaudado=arancel_recaudado),
			"por_actividad": _rows_from_buckets(actividad_buckets, label_key="actividad"),
		},
		"cto_comp": {
			**_kpi_slice_payload(emitido=cto_comp_emitido, recaudado=cto_comp_recaudado),
			"por_concepto": _concept_rows(cto_comp_buckets, tipo="CTO COMP"),
		},
		"federativa": {
			**_kpi_slice_payload(emitido=federativa_emitido, recaudado=federativa_recaudado),
			"por_concepto": _concept_rows(federativa_buckets, tipo="Federativa"),
		},
		"otros": {
			**_kpi_slice_payload(emitido=otros_emitido, recaudado=otros_recaudado),
			"por_concepto": _concept_rows(otros_buckets, tipo="Otro"),
		},
		"cobrabilidad_vistas": _cobrabilidad_vistas_payload(),
	}


def get_cobranza_panel_links(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Enlaces Desk para la card de cobrabilidad (spec informe_rendicion fase 3)."""
	ref = getdate(reference_date or today())
	first = get_first_day(ref)
	last = get_last_day(ref)
	periodo = format_periodo_cobro(ref)
	base_filters = {
		"fecha_desde": str(first),
		"fecha_hasta": str(last),
		"periodo_cobro": periodo,
	}

	def _report_link(**extra: Any) -> dict[str, Any]:
		return {
			"report": "Recaudacion por concepto",
			"filters": {**base_filters, **extra},
		}

	return {
		"periodo": periodo,
		"report_by_vista": {
			"total": _report_link(),
			"cuota": _report_link(solo_cuotas_sociales=1),
			"arancel": _report_link(agrupacion="Arancel"),
			"cto_comp": _report_link(agrupacion="CTO COMP"),
			"federativa": _report_link(agrupacion="Federativa"),
			"otro": _report_link(agrupacion="Otro"),
		},
		"recaudado_cuotas_report": _report_link(solo_cuotas_sociales=1),
		"recaudado_aranceles_report": _report_link(agrupacion="Arancel"),
		"rendicion_completa_report": _report_link(),
		"saldo_cuotas_socios_doctype": SOCIO_DOCTYPE,
		"saldo_cuotas_socios_filters": [["Socio", "saldo_deuda", ">", 0]],
	}


def get_cobrabilidad_payload(*, reference_date: str | date | None = None) -> dict[str, Any]:
	"""Card de cobrabilidad recalculada para el mes de `reference_date`."""
	ref = getdate(reference_date or today())
	return {
		"periodo": format_periodo_cobro(ref),
		"recaudacion": get_recaudacion_mes_payload(reference_date=ref),
		"cobranza": get_cobranza_panel_links(reference_date=ref),
	}


def get_panel_metricas_payload(
	*,
	reference_date: str | date | None = None,
	tendencia_reference_date: str | date | None = None,
	tendencia_vista: str | None = None,
) -> dict[str, Any]:
	ref = getdate(reference_date or today())
	tendencia_ref = getdate(tendencia_reference_date or ref)
	socios = get_socio_metricas_payload(reference_date=ref)
	recaudacion = get_recaudacion_mes_payload(reference_date=ref)
	return {
		"socios": socios,
		"recaudacion": recaudacion,
		"tendencia_recaudacion": get_recaudacion_tendencia_payload(
			reference_date=tendencia_ref,
			vista=tendencia_vista or "total",
		),
		"medios_pago": get_medios_pago_payload(reference_date=ref),
		"ver_mas": {
			"socios_morosos_doctype": SOCIO_DOCTYPE,
			"socios_morosos_filters": [["Socio", "estado", "=", "Moroso"]],
			"socios_total_doctype": SOCIO_DOCTYPE,
			"socios_total_filters": [["Socio", "estado", "!=", "Baja"]],
			"socios_deuda_doctype": SOCIO_DOCTYPE,
			"socios_deuda_filters": [["Socio", "saldo_deuda", ">", 0]],
			"solicitudes_doctype": "Solicitud Asociacion",
			"solicitudes_filters": [
				["Solicitud Asociacion", "workflow_state", "in", ["Pendiente", "Requiere Corrección"]]
			],
			"cobranza": get_cobranza_panel_links(reference_date=ref),
		},
	}
