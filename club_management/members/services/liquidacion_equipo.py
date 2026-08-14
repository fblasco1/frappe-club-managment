"""Consulta y liquidación manual de deuda por equipo / rango de fechas.

Spec: `club_management/specs/liquidacion_equipo_deuda_rango.md`
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.activities.services.inscripcion_socio import (
	INSCRIPCION_DOCTYPE,
	resolve_item_arancel_inscripcion,
)
from club_management.members.doctype.socio.socio import format_socio_nombre_completo
from club_management.members.services.cargo_extra_conceptos import federativa_item_codes_inscripcion
from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	SOCIO_DOCTYPE,
	_campo_socio_en,
	erpnext_cobranza_disponible,
	get_club_settings,
	registrar_cobro_manual,
	sync_saldo_deuda_socio,
)

PERIODO_COBRANZA_FIELDS = ("periodo_cobro", "custom_periodo_cobro")
ENTRENADOR_LIQUIDACION_RATIO = 0.8
SALES_INVOICE_ITEM_DOCTYPE = "Sales Invoice Item"


def _equipos_from_filters(filters: dict[str, Any] | frappe._dict) -> list[str]:
	filters = frappe._dict(filters or {})
	raw = filters.get("equipos_actividad")
	if raw:
		if isinstance(raw, str):
			raw = raw.strip()
			if raw.startswith("["):
				try:
					parsed = frappe.parse_json(raw)
					if isinstance(parsed, list):
						return [str(value).strip() for value in parsed if str(value).strip()]
				except Exception:
					pass
			return [part.strip() for part in raw.split(",") if part.strip()]
		if isinstance(raw, list):
			return [str(value).strip() for value in raw if str(value).strip()]
	if filters.get("equipo_actividad"):
		return [str(filters.equipo_actividad)]
	return []


def _filtro_jerarquico_informado(filters: dict[str, Any] | frappe._dict) -> bool:
	filters = frappe._dict(filters or {})
	return bool(
		filters.get("actividad")
		or filters.get("grupo_actividad")
		or filters.get("equipo_actividad")
		or _equipos_from_filters(filters)
	)


def validar_filtros_liquidacion(filters: dict[str, Any] | frappe._dict) -> None:
	"""Valida filtros comunes del reporte y las APIs de liquidación."""
	filters = frappe._dict(filters or {})
	fecha_desde = filters.get("fecha_desde")
	fecha_hasta = filters.get("fecha_hasta")
	if not fecha_desde or not fecha_hasta:
		frappe.throw(_("Indique fecha desde y fecha hasta."), frappe.ValidationError)

	desde = getdate(fecha_desde)
	hasta = getdate(fecha_hasta)
	if hasta < desde:
		frappe.throw(_("La fecha hasta debe ser posterior o igual a la fecha desde."), frappe.ValidationError)

	if not _filtro_jerarquico_informado(filters):
		frappe.throw(
			_("Debe elegir al menos una actividad, grupo o equipo."),
			frappe.ValidationError,
		)


def build_inscripcion_filters(filters: dict[str, Any] | frappe._dict) -> dict[str, Any]:
	validar_filtros_liquidacion(filters)
	filters = frappe._dict(filters)
	ins_filters: dict[str, Any] = {"estado": "Activa"}
	equipos = _equipos_from_filters(filters)
	if equipos:
		ins_filters["equipo_actividad"] = ["in", equipos] if len(equipos) > 1 else equipos[0]
	elif filters.get("grupo_actividad"):
		ins_filters["grupo_actividad"] = filters.grupo_actividad
	if filters.get("actividad"):
		ins_filters["actividad"] = filters.actividad
	return ins_filters


def _campo_periodo_cobro() -> str | None:
	for fieldname in PERIODO_COBRANZA_FIELDS:
		if frappe.get_meta(SALES_INVOICE_DOCTYPE).has_field(fieldname):
			return fieldname
	return None


def _factura_filters_socio(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
	*,
	solo_pendientes: bool = True,
) -> dict[str, Any]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		frappe.throw(_("Falta el campo Socio en Sales Invoice (ejecute migrate)."), frappe.ValidationError)

	filters: dict[str, Any] = {
		campo_socio: socio_name,
		"docstatus": 1,
		"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
	}
	if solo_pendientes:
		filters["outstanding_amount"] = [">", 0]
	return filters


def get_facturas_pendientes_socio_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> list[dict[str, Any]]:
	"""Facturas pendientes del socio con posting_date en el rango."""
	if not erpnext_cobranza_disponible():
		return []

	campo_periodo = _campo_periodo_cobro()
	fields = ["name", "posting_date", "due_date", "outstanding_amount", "grand_total"]
	if campo_periodo:
		fields.append(campo_periodo)

	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=_factura_filters_socio(socio_name, fecha_desde, fecha_hasta),
		fields=fields,
		order_by="posting_date asc, name asc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		result.append(
			{
				"name": row.name,
				"posting_date": row.posting_date,
				"due_date": row.due_date,
				"outstanding_amount": flt(row.outstanding_amount),
				"grand_total": flt(row.grand_total),
				"periodo_cobro": row.get(campo_periodo) if campo_periodo else None,
			}
		)
	return result


def calcular_deuda_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> tuple[float, int]:
	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	total = sum(flt(row["outstanding_amount"]) for row in facturas)
	return total, len(facturas)


def calcular_saldo_total_socio(socio_name: str) -> float:
	return sync_saldo_deuda_socio(socio_name)


def _cuota_social_item_codes() -> set[str]:
	settings = get_club_settings()
	codes = {settings.item_cuota_social}
	for row in settings.cuotas_categoria or []:
		if row.item:
			codes.add(row.item)
	return {code for code in codes if code}


def _default_pct_liquidacion_entrenador() -> float:
	settings = get_club_settings()
	pct = flt(settings.pct_liquidacion_entrenador_default)
	if pct <= 0:
		return ENTRENADOR_LIQUIDACION_RATIO * 100
	return pct


def resolve_pct_liquidacion_entrenador(
	*,
	equipo_actividad: str | None = None,
	grupo_actividad: str | None = None,
) -> float:
	"""Porcentaje efectivo (0–100) para liquidación del entrenador."""
	if equipo_actividad:
		pct = flt(frappe.db.get_value("Equipo Actividad", equipo_actividad, "pct_liquidacion_entrenador"))
		if pct > 0:
			return pct
	if grupo_actividad:
		pct = flt(frappe.db.get_value("Grupo Actividad", grupo_actividad, "pct_liquidacion_entrenador"))
		if pct > 0:
			return pct
	return _default_pct_liquidacion_entrenador()


def _outstanding_ratio(grand_total: float, outstanding_amount: float) -> float:
	grand = flt(grand_total)
	if grand <= 0:
		return 0.0
	return min(flt(outstanding_amount) / grand, 1.0)


def _invoice_lines_by_parent(parent_names: list[str]) -> dict[str, list[dict[str, Any]]]:
	if not parent_names:
		return {}
	rows = frappe.get_all(
		SALES_INVOICE_ITEM_DOCTYPE,
		filters={"parent": ["in", parent_names]},
		fields=["parent", "item_code", "amount"],
	)
	grouped: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def calcular_deuda_desglose_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
	*,
	inscripcion_name: str | None = None,
) -> dict[str, Any]:
	"""Desglose de deuda pendiente por concepto y meses en rango."""
	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	cuota_codes = _cuota_social_item_codes()
	arancel_codes: set[str] = set()
	federativa_codes: set[str] = set()
	if inscripcion_name:
		item_arancel = resolve_item_arancel_inscripcion(inscripcion_name)
		if item_arancel:
			from club_management.activities.data.voley_aranceles_icdpe import (
				expand_voley_arancel_item_codes,
			)

			arancel_codes.update(expand_voley_arancel_item_codes(item_arancel))
		federativa_codes.update(federativa_item_codes_inscripcion(inscripcion_name))

	cuota = arancel = federativa = 0.0
	periodos: set[str] = set()
	lines_by_parent = _invoice_lines_by_parent([row["name"] for row in facturas])
	for invoice in facturas:
		periodo = invoice.get("periodo_cobro")
		if periodo:
			periodos.add(str(periodo))
		ratio = _outstanding_ratio(invoice["grand_total"], invoice["outstanding_amount"])
		if ratio <= 0:
			continue
		for line in lines_by_parent.get(invoice["name"], []):
			amount = flt(line.get("amount")) * ratio
			code = line.get("item_code") or ""
			if code in cuota_codes:
				cuota += amount
			elif code in arancel_codes:
				arancel += amount
			elif code in federativa_codes:
				federativa += amount

	deuda_en_rango, cantidad_facturas = calcular_deuda_en_rango(socio_name, fecha_desde, fecha_hasta)
	cantidad_meses = len(periodos) if periodos else cantidad_facturas
	return {
		"deuda_cuota_social": round(cuota, 2),
		"deuda_arancel": round(arancel, 2),
		"deuda_cuota_federativa": round(federativa, 2),
		"deuda_en_rango": deuda_en_rango,
		"cantidad_meses_deuda": cantidad_meses,
		"cantidad_facturas": cantidad_facturas,
	}


def _inscripciones_por_socio(filters: dict[str, Any] | frappe._dict) -> dict[str, list[dict[str, Any]]]:
	ins_filters = build_inscripcion_filters(filters)
	rows = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters=ins_filters,
		fields=[
			"name",
			"socio",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
		],
		order_by="modified desc",
	)
	by_socio: dict[str, list[dict[str, Any]]] = {}
	for row in rows:
		by_socio.setdefault(row.socio, []).append(row)
	return by_socio


def _inscripcion_principal(inscripciones: list[dict[str, Any]]) -> dict[str, Any]:
	for row in inscripciones:
		if row.get("equipo_actividad"):
			return row
	return inscripciones[0]


def get_deuda_por_equipo_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Deuda por equipo»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de deuda requiere ERPNext (Sales Invoice)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	validar_filtros_liquidacion(filters)
	inscripciones = _inscripciones_por_socio(filters)
	if not inscripciones:
		return []

	socio_names = list(inscripciones.keys())
	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "estado": ["!=", "Baja"]},
		fields=["name", "nombre", "apellido", "estado"],
	)
	socio_by_name = {row.name: row for row in socios}

	rows: list[dict[str, Any]] = []
	for socio_name, ins_list in inscripciones.items():
		socio = socio_by_name.get(socio_name)
		if not socio:
			continue
		ins = _inscripcion_principal(ins_list)
		desglose = calcular_deuda_desglose_en_rango(
			socio_name,
			str(filters.fecha_desde),
			str(filters.fecha_hasta),
			inscripcion_name=ins.name,
		)
		if not int(filters.get("incluir_saldo_cero") or 0) and desglose["deuda_en_rango"] <= 0:
			continue

		nombre_apellido = format_socio_nombre_completo(socio.apellido, socio.nombre) or socio_name

		rows.append(
			{
				"socio": socio_name,
				"nombre_apellido": nombre_apellido,
				"estado": socio.estado,
				"actividad": ins.actividad,
				"grupo_actividad": ins.grupo_actividad or "",
				"equipo_actividad": ins.equipo_actividad or "",
				**desglose,
				"saldo_total": calcular_saldo_total_socio(socio_name),
			}
		)

	rows.sort(key=lambda row: (-flt(row["deuda_en_rango"]), row["nombre_apellido"].lower()))
	return rows


def calcular_pagos_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
	*,
	item_arancel: str | None = None,
	inscripcion_name: str | None = None,
) -> tuple[float, int]:
	"""Suma aranceles cobrados del socio en el rango (solo líneas del ítem de arancel)."""
	if inscripcion_name and not item_arancel:
		item_arancel = resolve_item_arancel_inscripcion(inscripcion_name)
	return calcular_pagos_arancel_en_rango(
		socio_name,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		item_arancel=item_arancel,
	)


def calcular_pagos_arancel_en_rango(
	socio_name: str,
	*,
	fecha_desde: str,
	fecha_hasta: str,
	item_arancel: str | None,
) -> tuple[float, int]:
	"""Importe cobrado de líneas de factura que coinciden con el ítem de arancel."""
	if not item_arancel or not erpnext_cobranza_disponible():
		return 0.0, 0

	from club_management.activities.data.voley_aranceles_icdpe import (
		expand_voley_arancel_item_codes,
	)

	item_codes = list(expand_voley_arancel_item_codes(item_arancel))
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return 0.0, 0

	invoices = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
		},
		fields=["name", "grand_total", "outstanding_amount"],
	)
	total = 0.0
	count = 0
	for invoice in invoices:
		paid = flt(invoice.grand_total) - flt(invoice.outstanding_amount)
		if paid <= 0:
			continue
		lines = frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": invoice.name, "item_code": ["in", item_codes]},
			fields=["amount"],
		)
		arancel_amount = sum(flt(line.amount) for line in lines)
		if arancel_amount <= 0:
			continue
		grand_total = flt(invoice.grand_total)
		if grand_total <= 0:
			continue
		paid_ratio = min(paid / grand_total, 1.0)
		total += arancel_amount * paid_ratio
		count += 1
	return total, count


def _calcular_liquidacion_entrenador_inscripciones(
	inscripciones: list[dict[str, Any]],
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> tuple[float, float, float]:
	"""Retorna (pagos_en_rango, liquidacion_entrenador, pct_promedio_ponderado)."""
	pagos_total = 0.0
	liquidacion_total = 0.0
	processed_items: set[str] = set()
	for ins in inscripciones:
		item_arancel = resolve_item_arancel_inscripcion(ins.name)
		if not item_arancel or item_arancel in processed_items:
			continue
		processed_items.add(item_arancel)
		pct = resolve_pct_liquidacion_entrenador(
			equipo_actividad=ins.equipo_actividad,
			grupo_actividad=ins.grupo_actividad,
		)
		pagos, _count = calcular_pagos_arancel_en_rango(
			socio_name,
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
			item_arancel=item_arancel,
		)
		if pagos <= 0:
			continue
		pagos_total += pagos
		liquidacion_total += pagos * (pct / 100.0)
	pct_efectivo = (liquidacion_total / pagos_total * 100.0) if pagos_total > 0 else 0.0
	return round(pagos_total, 2), round(liquidacion_total, 2), round(pct_efectivo, 1)


def get_pagos_por_equipo_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Pagos por equipo»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de pagos requiere ERPNext (Payment Entry)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	validar_filtros_liquidacion(filters)
	inscripciones = _inscripciones_por_socio(filters)
	if not inscripciones:
		return []

	socio_names = list(inscripciones.keys())
	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names], "estado": ["!=", "Baja"]},
		fields=["name", "nombre", "apellido", "estado"],
	)
	socio_by_name = {row.name: row for row in socios}

	rows: list[dict[str, Any]] = []
	for socio_name, ins_list in inscripciones.items():
		socio = socio_by_name.get(socio_name)
		if not socio:
			continue

		pagos_en_rango, liquidacion_entrenador, pct_entrenador = _calcular_liquidacion_entrenador_inscripciones(
			ins_list,
			socio_name,
			str(filters.fecha_desde),
			str(filters.fecha_hasta),
		)
		cantidad = sum(
			calcular_pagos_en_rango(
				socio_name,
				str(filters.fecha_desde),
				str(filters.fecha_hasta),
				inscripcion_name=ins.name,
			)[1]
			for ins in ins_list
		)
		if not int(filters.get("incluir_saldo_cero") or 0) and pagos_en_rango <= 0:
			continue

		ins = _inscripcion_principal(ins_list)
		nombre_apellido = format_socio_nombre_completo(socio.apellido, socio.nombre) or socio_name

		rows.append(
			{
				"socio": socio_name,
				"nombre_apellido": nombre_apellido,
				"estado": socio.estado,
				"actividad": ins.actividad,
				"grupo_actividad": ins.grupo_actividad or "",
				"equipo_actividad": ins.equipo_actividad or "",
				"pagos_en_rango": pagos_en_rango,
				"pct_entrenador": pct_entrenador,
				"liquidacion_entrenador": liquidacion_entrenador,
				"cantidad_pagos": cantidad,
			}
		)

	rows.sort(key=lambda row: (-flt(row["pagos_en_rango"]), row["nombre_apellido"].lower()))
	return rows


def get_pagos_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 140},
		{"label": _("Apellido, nombre/s"), "fieldname": "nombre_apellido", "fieldtype": "Data", "width": 200},
		{"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 110},
		{"label": _("Actividad"), "fieldname": "actividad", "fieldtype": "Link", "options": "Actividad", "width": 140},
		{
			"label": _("Grupo / tira"),
			"fieldname": "grupo_actividad",
			"fieldtype": "Link",
			"options": "Grupo Actividad",
			"width": 140,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_actividad",
			"fieldtype": "Link",
			"options": "Equipo Actividad",
			"width": 140,
		},
		{
			"label": _("Arancel pagado en rango"),
			"fieldname": "pagos_en_rango",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("% entrenador"),
			"fieldname": "pct_entrenador",
			"fieldtype": "Percent",
			"width": 110,
		},
		{
			"label": _("Liquidación entrenador"),
			"fieldname": "liquidacion_entrenador",
			"fieldtype": "Currency",
			"width": 180,
		},
		{
			"label": _("Facturas con arancel cobrado"),
			"fieldname": "cantidad_pagos",
			"fieldtype": "Int",
			"width": 150,
		},
	]


def get_report_columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 140},
		{"label": _("Apellido, nombre/s"), "fieldname": "nombre_apellido", "fieldtype": "Data", "width": 200},
		{"label": _("Estado"), "fieldname": "estado", "fieldtype": "Data", "width": 110},
		{"label": _("Actividad"), "fieldname": "actividad", "fieldtype": "Link", "options": "Actividad", "width": 140},
		{
			"label": _("Grupo / tira"),
			"fieldname": "grupo_actividad",
			"fieldtype": "Link",
			"options": "Grupo Actividad",
			"width": 140,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_actividad",
			"fieldtype": "Link",
			"options": "Equipo Actividad",
			"width": 140,
		},
		{
			"label": _("Deuda en rango"),
			"fieldname": "deuda_en_rango",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Cuota social"),
			"fieldname": "deuda_cuota_social",
			"fieldtype": "Currency",
			"width": 120,
		},
		{
			"label": _("Arancel actividad"),
			"fieldname": "deuda_arancel",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Cuota federativa"),
			"fieldname": "deuda_cuota_federativa",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Meses deuda"),
			"fieldname": "cantidad_meses_deuda",
			"fieldtype": "Int",
			"width": 100,
		},
		{"label": _("Saldo total"), "fieldname": "saldo_total", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Facturas pendientes"),
			"fieldname": "cantidad_facturas",
			"fieldtype": "Int",
			"width": 120,
		},
	]


def _sum_currency(rows: list[dict[str, Any]], fieldname: str) -> float:
	return round(sum(flt(row.get(fieldname)) for row in rows), 2)


def get_deuda_report_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{
			"value": _sum_currency(rows, "deuda_en_rango"),
			"label": _("Deuda total en rango"),
			"datatype": "Currency",
			"indicator": "red",
		},
		{
			"value": _sum_currency(rows, "deuda_cuota_social"),
			"label": _("Cuota social"),
			"datatype": "Currency",
		},
		{
			"value": _sum_currency(rows, "deuda_arancel"),
			"label": _("Aranceles"),
			"datatype": "Currency",
		},
		{
			"value": _sum_currency(rows, "deuda_cuota_federativa"),
			"label": _("Cuota federativa"),
			"datatype": "Currency",
		},
	]


def get_pagos_report_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{
			"value": _sum_currency(rows, "pagos_en_rango"),
			"label": _("Arancel cobrado"),
			"datatype": "Currency",
			"indicator": "green",
		},
		{
			"value": _sum_currency(rows, "liquidacion_entrenador"),
			"label": _("Liquidación entrenadores"),
			"datatype": "Currency",
		},
	]


def get_deuda_por_actividad_report_columns() -> list[dict[str, Any]]:
	return [
		{
			"label": _("Actividad"),
			"fieldname": "actividad",
			"fieldtype": "Link",
			"options": "Actividad",
			"width": 180,
		},
		{
			"label": _("Deuda cuota social"),
			"fieldname": "deuda_cuota_social",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Deuda aranceles"),
			"fieldname": "deuda_arancel",
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"label": _("Deuda cuota federativa"),
			"fieldname": "deuda_cuota_federativa",
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"label": _("Deuda total"),
			"fieldname": "deuda_total",
			"fieldtype": "Currency",
			"width": 130,
		},
		{
			"label": _("Socios deudores"),
			"fieldname": "socios_deudores",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Prom. meses deuda"),
			"fieldname": "promedio_meses_deuda",
			"fieldtype": "Float",
			"width": 130,
		},
	]


def get_deuda_por_actividad_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Deuda por actividad»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de deuda requiere ERPNext (Sales Invoice)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	fecha_desde = filters.get("fecha_desde")
	fecha_hasta = filters.get("fecha_hasta")
	if not fecha_desde or not fecha_hasta:
		frappe.throw(_("Indique fecha desde y fecha hasta."), frappe.ValidationError)
	if getdate(fecha_hasta) < getdate(fecha_desde):
		frappe.throw(_("La fecha hasta debe ser posterior o igual a la fecha desde."), frappe.ValidationError)

	actividades = frappe.get_all("Actividad", filters={"habilitada": 1}, pluck="name")
	rows: list[dict[str, Any]] = []
	for actividad in actividades:
		socios_ins = _inscripciones_por_socio(
			{
				"actividad": actividad,
				"fecha_desde": fecha_desde,
				"fecha_hasta": fecha_hasta,
			}
		)
		if not socios_ins:
			continue

		totales = {
			"deuda_cuota_social": 0.0,
			"deuda_arancel": 0.0,
			"deuda_cuota_federativa": 0.0,
			"deuda_total": 0.0,
		}
		meses_deuda: list[int] = []
		socios_deudores = 0
		for socio_name, ins_list in socios_ins.items():
			if frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado") == "Baja":
				continue
			ins = _inscripcion_principal(ins_list)
			desglose = calcular_deuda_desglose_en_rango(
				socio_name,
				str(fecha_desde),
				str(fecha_hasta),
				inscripcion_name=ins.name,
			)
			if desglose["deuda_en_rango"] <= 0:
				continue
			socios_deudores += 1
			meses_deuda.append(int(desglose["cantidad_meses_deuda"]))
			totales["deuda_cuota_social"] += desglose["deuda_cuota_social"]
			totales["deuda_arancel"] += desglose["deuda_arancel"]
			totales["deuda_cuota_federativa"] += desglose["deuda_cuota_federativa"]
			totales["deuda_total"] += desglose["deuda_en_rango"]

		if socios_deudores <= 0:
			continue

		promedio = round(sum(meses_deuda) / socios_deudores, 1) if meses_deuda else 0.0
		rows.append(
			{
				"actividad": actividad,
				"deuda_cuota_social": round(totales["deuda_cuota_social"], 2),
				"deuda_arancel": round(totales["deuda_arancel"], 2),
				"deuda_cuota_federativa": round(totales["deuda_cuota_federativa"], 2),
				"deuda_total": round(totales["deuda_total"], 2),
				"socios_deudores": socios_deudores,
				"promedio_meses_deuda": promedio,
			}
		)

	rows.sort(key=lambda row: (-flt(row["deuda_total"]), row["actividad"]))
	total_row = {
		"actividad": _("Total"),
		"deuda_cuota_social": _sum_currency(rows, "deuda_cuota_social"),
		"deuda_arancel": _sum_currency(rows, "deuda_arancel"),
		"deuda_cuota_federativa": _sum_currency(rows, "deuda_cuota_federativa"),
		"deuda_total": _sum_currency(rows, "deuda_total"),
		"socios_deudores": sum(int(row["socios_deudores"]) for row in rows),
		"promedio_meses_deuda": 0.0,
	}
	if rows:
		total_meses = sum(
			flt(row["promedio_meses_deuda"]) * int(row["socios_deudores"]) for row in rows
		)
		total_deudores = sum(int(row["socios_deudores"]) for row in rows)
		if total_deudores:
			total_row["promedio_meses_deuda"] = round(total_meses / total_deudores, 1)
	rows.append(total_row)
	return rows


def assert_factura_liquidable_en_rango(
	socio_name: str,
	sales_invoice_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> None:
	"""Valida socio, rango y saldo pendiente antes de registrar cobro."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, sales_invoice_name)
	if campo_socio and invoice.get(campo_socio) != socio_name:
		frappe.throw(_("La factura no pertenece a este socio."), frappe.ValidationError)

	posting = getdate(invoice.posting_date)
	desde = getdate(fecha_desde)
	hasta = getdate(fecha_hasta)
	if posting < desde or posting > hasta:
		frappe.throw(_("La factura no pertenece al rango de fechas indicado."), frappe.ValidationError)

	if flt(invoice.outstanding_amount) <= 0:
		frappe.throw(_("La factura no tiene saldo pendiente."), frappe.ValidationError)


def registrar_cobro_liquidacion(
	socio_name: str,
	sales_invoice_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	assert_factura_liquidable_en_rango(socio_name, sales_invoice_name, fecha_desde, fecha_hasta)
	payment_entry = registrar_cobro_manual(socio_name, sales_invoice_name)
	saldo = sync_saldo_deuda_socio(socio_name)
	deuda_en_rango, _cantidad = calcular_deuda_en_rango(socio_name, fecha_desde, fecha_hasta)
	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	return {
		"payment_entry": payment_entry,
		"saldo_total": saldo,
		"deuda_en_rango": deuda_en_rango,
		"estado": estado,
	}


def liquidar_deuda_socio_en_rango(
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> dict[str, Any]:
	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	payment_entries: list[str] = []
	for row in facturas:
		result = registrar_cobro_liquidacion(
			socio_name,
			row["name"],
			fecha_desde,
			fecha_hasta,
		)
		payment_entries.append(result["payment_entry"])

	saldo = sync_saldo_deuda_socio(socio_name)
	deuda_en_rango, cantidad = calcular_deuda_en_rango(socio_name, fecha_desde, fecha_hasta)
	estado = frappe.db.get_value(SOCIO_DOCTYPE, socio_name, "estado")
	return {
		"payment_entries": payment_entries,
		"saldo_total": saldo,
		"deuda_en_rango": deuda_en_rango,
		"cantidad_facturas": cantidad,
		"estado": estado,
	}


def default_report_filters() -> dict[str, str | int]:
	first_day = getdate(today()).replace(day=1)
	return {
		"fecha_desde": str(first_day),
		"fecha_hasta": str(today()),
		"incluir_saldo_cero": 0,
	}
