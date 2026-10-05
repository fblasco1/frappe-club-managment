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
from club_management.members.data.cuotas_sociales_vigentes import CUOTA_SOCIAL_LEGACY_ITEM_CODE
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
	codes = {settings.item_cuota_social, CUOTA_SOCIAL_LEGACY_ITEM_CODE}
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
			from club_management.activities.data.basquet_aranceles_icdpe import (
				expand_arancel_item_codes_for_pagos,
			)

			arancel_codes.update(expand_arancel_item_codes_for_pagos(item_arancel))
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


def _inscripciones_por_socio(
	filters: dict[str, Any] | frappe._dict,
	*,
	incluir_bajas_desde: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
	"""Inscripciones activas del filtro; opcionalmente también las pasadas a `Baja`
	desde `incluir_bajas_desde` (la baja es la última modificación de la inscripción)."""
	ins_filters = build_inscripcion_filters(filters)
	fields = ["name", "socio", "actividad", "grupo_actividad", "equipo_actividad", "estado"]
	rows = frappe.get_all(INSCRIPCION_DOCTYPE, filters=ins_filters, fields=fields, order_by="modified desc")
	if incluir_bajas_desde:
		bajas_filters = {
			**ins_filters,
			"estado": "Baja",
			"modified": [">=", f"{getdate(incluir_bajas_desde)} 00:00:00"],
		}
		rows += frappe.get_all(
			INSCRIPCION_DOCTYPE, filters=bajas_filters, fields=fields, order_by="modified desc"
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


def _facturas_con_pe_en_rango(socio_name: str, fecha_desde: str, fecha_hasta: str) -> list[str]:
	"""Facturas del socio con al menos un PE en el rango (fecha de cobro)."""
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	return frappe.db.sql_list(
		f"""
		SELECT DISTINCT per.reference_name
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name AND si.docstatus = 1
		WHERE per.reference_doctype = %s
		  AND pe.posting_date BETWEEN %s AND %s
		  AND si.`{campo_socio}` = %s
		ORDER BY per.reference_name
		""",
		(SALES_INVOICE_DOCTYPE, getdate(fecha_desde), getdate(fecha_hasta), socio_name),
	)


def _pagos_arancel_detalle(
	socio_name: str,
	*,
	fecha_desde: str,
	fecha_hasta: str,
	item_arancel: str | None,
) -> list[tuple[str, float]]:
	"""Facturas con arancel cobrado en rango: `[(invoice, cobrado), …]`."""
	if not item_arancel or not erpnext_cobranza_disponible():
		return []

	from club_management.activities.data.basquet_aranceles_icdpe import (
		expand_arancel_item_codes_for_pagos,
	)
	from club_management.scripts.informe_concepto_cobranza import monto_cobrado_de_items_en_rango

	item_codes = list(expand_arancel_item_codes_for_pagos(item_arancel))
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []

	detalle: list[tuple[str, float]] = []
	for invoice_name in _facturas_con_pe_en_rango(socio_name, fecha_desde, fecha_hasta):
		cobrado = monto_cobrado_de_items_en_rango(
			invoice_name,
			item_codes,
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
		)
		if cobrado <= 0.005:
			continue
		detalle.append((invoice_name, flt(cobrado, 2)))
	return detalle


def calcular_pagos_arancel_en_rango(
	socio_name: str,
	*,
	fecha_desde: str,
	fecha_hasta: str,
	item_arancel: str | None,
) -> tuple[float, int]:
	"""Importe cobrado de arancel según PE en rango (incluye mora del concepto)."""
	detalle = _pagos_arancel_detalle(
		socio_name,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		item_arancel=item_arancel,
	)
	total = flt(sum(cobrado for _inv, cobrado in detalle), 2)
	return total, len(detalle)


def _periodos_de_facturas(invoice_names: set[str]) -> list[str]:
	campo_periodo = _campo_periodo_cobro()
	if not campo_periodo or not invoice_names:
		return []
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={"name": ["in", list(invoice_names)]},
		fields=[campo_periodo],
	)
	periodos = {str(row.get(campo_periodo) or "").strip() for row in rows}
	return sorted(p for p in periodos if p and not p.endswith("-MORA"))


def _calcular_liquidacion_entrenador_inscripciones(
	inscripciones: list[dict[str, Any]],
	socio_name: str,
	fecha_desde: str,
	fecha_hasta: str,
) -> tuple[float, float, float, set[str], list[str]]:
	"""Retorna (pagos, liquidación, pct ponderado, facturas únicas, períodos cobrados).

	El importe de cada ítem de arancel se cuenta una sola vez aunque el socio
	tenga varias inscripciones que compartan el ítem; en ese caso se liquida
	con el mayor % entre las inscripciones del filtro (determinista).
	"""
	pct_por_item: dict[str, float] = {}
	for ins in inscripciones:
		item_arancel = resolve_item_arancel_inscripcion(ins.name)
		if not item_arancel:
			continue
		pct = resolve_pct_liquidacion_entrenador(
			equipo_actividad=ins.equipo_actividad,
			grupo_actividad=ins.grupo_actividad,
		)
		if item_arancel not in pct_por_item or pct > pct_por_item[item_arancel]:
			pct_por_item[item_arancel] = pct

	pagos_total = 0.0
	liquidacion_total = 0.0
	facturas: set[str] = set()
	for item_arancel, pct in pct_por_item.items():
		detalle = _pagos_arancel_detalle(
			socio_name,
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
			item_arancel=item_arancel,
		)
		pagos = flt(sum(cobrado for _inv, cobrado in detalle), 2)
		if pagos <= 0:
			continue
		pagos_total += pagos
		liquidacion_total += pagos * (pct / 100.0)
		facturas.update(inv for inv, _cobrado in detalle)
	pct_efectivo = (liquidacion_total / pagos_total * 100.0) if pagos_total > 0 else 0.0
	periodos = _periodos_de_facturas(facturas)
	return (
		round(pagos_total, 2),
		round(liquidacion_total, 2),
		round(pct_efectivo, 1),
		facturas,
		periodos,
	)


def total_arancel_cobrado_en_rango(fecha_desde: str, fecha_hasta: str) -> float:
	"""Total de arancel deportivo imputado por fecha de PE en el rango (sin filtro de equipo).

	Conciliación contra el subtotal de aranceles del CSV consolidado
	(spec `pagos_por_equipo.md`).
	"""
	if not erpnext_cobranza_disponible():
		return 0.0

	from club_management.activities.data.basquet_aranceles_icdpe import (
		expand_arancel_item_codes_for_pagos,
	)
	from club_management.scripts.informe_concepto_cobranza import monto_cobrado_de_items_en_rango

	arancel_codes: set[str] = set()
	for doctype in ("Actividad", "Grupo Actividad", "Equipo Actividad"):
		for code in frappe.get_all(
			doctype, filters={"item": ["!=", ""]}, pluck="item"
		):
			if code:
				arancel_codes.update(expand_arancel_item_codes_for_pagos(code))
	if not arancel_codes:
		return 0.0

	invoice_names = frappe.db.sql_list(
		"""
		SELECT DISTINCT per.reference_name
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent AND pe.docstatus = 1
		INNER JOIN `tabSales Invoice` si ON si.name = per.reference_name AND si.docstatus = 1
		WHERE per.reference_doctype = %s
		  AND pe.posting_date BETWEEN %s AND %s
		""",
		(SALES_INVOICE_DOCTYPE, getdate(fecha_desde), getdate(fecha_hasta)),
	)
	codes = list(arancel_codes)
	total = 0.0
	for invoice_name in invoice_names:
		total += monto_cobrado_de_items_en_rango(
			invoice_name,
			codes,
			fecha_desde=fecha_desde,
			fecha_hasta=fecha_hasta,
		)
	return flt(total, 2)


def get_pagos_por_equipo_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Filas del Script Report «Pagos por equipo»."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de pagos requiere ERPNext (Payment Entry)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	validar_filtros_liquidacion(filters)
	inscripciones = _inscripciones_por_socio(filters, incluir_bajas_desde=str(filters.fecha_desde))
	if not inscripciones:
		return []

	socio_names = list(inscripciones.keys())
	socios = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", socio_names]},
		fields=["name", "nombre", "apellido", "estado"],
	)
	socio_by_name = {row.name: row for row in socios}

	rows: list[dict[str, Any]] = []
	for socio_name, ins_list in inscripciones.items():
		socio = socio_by_name.get(socio_name)
		if not socio:
			continue
		tiene_activa = socio.estado != "Baja" and any(ins.estado == "Activa" for ins in ins_list)

		(
			pagos_en_rango,
			liquidacion_entrenador,
			pct_entrenador,
			facturas,
			periodos,
		) = _calcular_liquidacion_entrenador_inscripciones(
			ins_list,
			socio_name,
			str(filters.fecha_desde),
			str(filters.fecha_hasta),
		)
		if pagos_en_rango <= 0 and not (int(filters.get("incluir_saldo_cero") or 0) and tiene_activa):
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
				"cantidad_pagos": len(facturas),
				"periodos_cobrados": ", ".join(periodos),
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
		{
			"label": _("Períodos cobrados"),
			"fieldname": "periodos_cobrados",
			"fieldtype": "Data",
			"width": 140,
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
		{"label": _("Nivel"), "fieldname": "nivel", "fieldtype": "Data", "width": 280},
		{"label": _("Socio"), "fieldname": "socio", "fieldtype": "Link", "options": "Socio", "width": 120},
		{
			"label": _("Actividad"),
			"fieldname": "actividad",
			"fieldtype": "Link",
			"options": "Actividad",
			"width": 150,
		},
		{
			"label": _("Grupo / tira"),
			"fieldname": "grupo_actividad",
			"fieldtype": "Link",
			"options": "Grupo Actividad",
			"width": 150,
		},
		{
			"label": _("Equipo / categoría"),
			"fieldname": "equipo_actividad",
			"fieldtype": "Link",
			"options": "Equipo Actividad",
			"width": 160,
		},
		{"label": _("Actividades"), "fieldname": "actividades", "fieldtype": "Data", "width": 180},
		{"label": _("Cuota social"), "fieldname": "deuda_cuota_social", "fieldtype": "Currency", "width": 130},
		{"label": _("Arancel"), "fieldname": "deuda_arancel", "fieldtype": "Currency", "width": 130},
		{"label": _("Total"), "fieldname": "deuda_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Socios deudores"), "fieldname": "socios_deudores", "fieldtype": "Data", "width": 130},
		{"label": _("indent"), "fieldname": "indent", "fieldtype": "Int", "width": 0, "hidden": 1},
	]


def _titulo_doc(doctype: str, name: str) -> str:
	if not name:
		return ""
	titulo = frappe.db.get_value(doctype, name, "titulo")
	return str(titulo or name)


def _nombres_socios(socio_names: set[str]) -> dict[str, str]:
	"""Mapa socio.name → 'Apellido, Nombre' para filas hoja del informe."""
	if not socio_names:
		return {}
	rows = frappe.get_all(
		SOCIO_DOCTYPE,
		filters={"name": ["in", list(socio_names)]},
		fields=["name", "nombre", "apellido"],
	)
	return {
		row.name: format_socio_nombre_completo(row.apellido, row.nombre) or row.name for row in rows
	}


def _fmt_socios_deudores(deudores: int, total_categoria: int) -> str:
	"""Cantidad de deudores y % sobre el padrón activo de la categoría."""
	if total_categoria <= 0:
		return str(int(deudores))
	pct = int(round(100.0 * int(deudores) / int(total_categoria)))
	return f"{int(deudores)} ({pct}%)"


_TOLERANCIA_DEUDA = 0.005


def _socios_con_facturas_pendientes_en_rango(fecha_desde: str, fecha_hasta: str) -> set[str]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return set()
	return set(
		frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={
				"docstatus": 1,
				"outstanding_amount": [">", 0],
				"posting_date": ["between", [getdate(fecha_desde), getdate(fecha_hasta)]],
				campo_socio: ["is", "set"],
			},
			pluck=campo_socio,
			distinct=True,
			order_by=campo_socio,
		)
	)


def _deuda_por_item_en_rango(socio_name: str, fecha_desde: str, fecha_hasta: str) -> dict[str, float]:
	"""Saldo impago por `item_code` en facturas pendientes del rango.

	Con cobros parciales se usa la imputación por línea (igual que «Deuda cuotas sociales»).
	"""
	from club_management.scripts.informe_concepto_cobranza import _cobros_imputados_por_linea

	facturas = get_facturas_pendientes_socio_en_rango(socio_name, fecha_desde, fecha_hasta)
	lines_by_parent = _invoice_lines_by_parent([row["name"] for row in facturas])
	por_item: dict[str, float] = {}
	for invoice in facturas:
		if flt(invoice["outstanding_amount"]) + _TOLERANCIA_DEUDA < flt(invoice["grand_total"]):
			lineas = [
				(row.get("item_code") or "", flt(row.get("restante")))
				for row in _cobros_imputados_por_linea(invoice["name"])
			]
		else:
			lineas = [
				(line.get("item_code") or "", flt(line.get("amount")))
				for line in lines_by_parent.get(invoice["name"], [])
			]
		for code, monto in lineas:
			if monto > 0:
				por_item[code] = por_item.get(code, 0.0) + monto
	return por_item


def _arancel_codes_inscripcion(inscripcion_name: str) -> set[str]:
	item_arancel = resolve_item_arancel_inscripcion(inscripcion_name)
	if not item_arancel:
		return set()
	from club_management.activities.data.basquet_aranceles_icdpe import (
		expand_arancel_item_codes_for_pagos,
	)

	return set(expand_arancel_item_codes_for_pagos(item_arancel))


def _sumar_deuda(destino: dict[str, float], cuota: float, arancel: float) -> None:
	destino["cuota"] = destino.get("cuota", 0.0) + cuota
	destino["arancel"] = destino.get("arancel", 0.0) + arancel


def _totales_socios(socios: dict[str, dict[str, float]]) -> tuple[float, float]:
	cuota = sum(flt(row.get("cuota")) for row in socios.values())
	arancel = sum(flt(row.get("arancel")) for row in socios.values())
	return round(cuota, 2), round(arancel, 2)


def _fila_deuda_actividad(
	nivel: str,
	indent: int,
	cuota: float,
	arancel: float,
	socios_deudores: str,
	*,
	socio: str = "",
	actividad: str = "",
	grupo: str = "",
	equipo: str = "",
	actividades: str = "",
) -> dict[str, Any]:
	return {
		"nivel": nivel,
		"socio": socio,
		"actividad": actividad,
		"grupo_actividad": grupo,
		"equipo_actividad": equipo,
		"actividades": actividades,
		"deuda_cuota_social": round(flt(cuota), 2),
		"deuda_arancel": round(flt(arancel), 2),
		"deuda_total": round(flt(cuota) + flt(arancel), 2),
		"socios_deudores": socios_deudores,
		"indent": indent,
	}


def get_deuda_por_actividad_data(filters: dict[str, Any] | frappe._dict) -> list[dict[str, Any]]:
	"""Deuda (cuota social + arancel) por actividad.

	Árbol Total → actividad → grupo → equipo → socio; los socios con más de una actividad
	van al agregado «Multiactividad» y los que no tienen actividad a «Sin actividad».
	"""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("La consulta de deuda requiere ERPNext (Sales Invoice)."), frappe.ValidationError)

	filters = frappe._dict(filters or {})
	fecha_desde = filters.get("fecha_desde")
	fecha_hasta = filters.get("fecha_hasta")
	if not fecha_desde or not fecha_hasta:
		frappe.throw(_("Indique fecha desde y fecha hasta."), frappe.ValidationError)
	if getdate(fecha_hasta) < getdate(fecha_desde):
		frappe.throw(_("La fecha hasta debe ser posterior o igual a la fecha desde."), frappe.ValidationError)
	desde, hasta = str(fecha_desde), str(fecha_hasta)
	filtro_actividad = filters.get("actividad")

	inscripciones = frappe.get_all(
		INSCRIPCION_DOCTYPE,
		filters={"estado": "Activa"},
		fields=["name", "socio", "actividad", "grupo_actividad", "equipo_actividad"],
		order_by="creation asc, name asc",
	)
	estados: dict[str, str] = {}
	if inscripciones:
		estados = dict(
			frappe.get_all(
				SOCIO_DOCTYPE,
				filters={"name": ["in", list({ins.socio for ins in inscripciones})]},
				fields=["name", "estado"],
				as_list=True,
			)
		)
	inscripciones_por_socio: dict[str, list[dict[str, Any]]] = {}
	for ins in inscripciones:
		if estados.get(ins.socio) in (None, "Baja"):
			continue
		inscripciones_por_socio.setdefault(ins.socio, []).append(ins)

	socios_con_deuda = _socios_con_facturas_pendientes_en_rango(desde, hasta)
	cuota_codes = _cuota_social_item_codes()

	# Padrón activo por (actividad, grupo, equipo) de socios de una sola actividad — incluye no deudores
	universo: dict[tuple[str, str, str], set[str]] = {}
	# (actividad, grupo, equipo) -> {socio: {cuota, arancel}}
	buckets: dict[tuple[str, str, str], dict[str, dict[str, float]]] = {}
	multi_padron: set[str] = set()
	multi_socios: dict[str, dict[str, float]] = {}
	multi_actividades: dict[str, list[str]] = {}

	for socio_name, ins_list in inscripciones_por_socio.items():
		actividades = list(dict.fromkeys(str(ins.actividad or "") for ins in ins_list))
		if filtro_actividad and filtro_actividad not in actividades:
			continue
		es_multi = len(actividades) > 1
		if es_multi:
			multi_padron.add(socio_name)
			multi_actividades[socio_name] = actividades
		else:
			for ins in ins_list:
				key = (str(ins.actividad or ""), str(ins.grupo_actividad or ""), str(ins.equipo_actividad or ""))
				universo.setdefault(key, set()).add(socio_name)
		if socio_name not in socios_con_deuda:
			continue

		por_item = _deuda_por_item_en_rango(socio_name, desde, hasta)
		cuota = sum(monto for code, monto in por_item.items() if code in cuota_codes)
		usados: set[str] = set(cuota_codes)
		aranceles: list[float] = []
		for ins in ins_list:
			codes = _arancel_codes_inscripcion(ins.name) - usados
			usados |= codes
			aranceles.append(sum(por_item.get(code, 0.0) for code in codes))

		if es_multi:
			if cuota + sum(aranceles) > _TOLERANCIA_DEUDA:
				_sumar_deuda(multi_socios.setdefault(socio_name, {}), cuota, sum(aranceles))
			continue
		for idx, ins in enumerate(ins_list):
			cuota_ins = cuota if idx == 0 else 0.0
			if cuota_ins + aranceles[idx] <= _TOLERANCIA_DEUDA:
				continue
			key = (str(ins.actividad or ""), str(ins.grupo_actividad or ""), str(ins.equipo_actividad or ""))
			_sumar_deuda(buckets.setdefault(key, {}).setdefault(socio_name, {}), cuota_ins, aranceles[idx])

	sin_actividad_socios: dict[str, dict[str, float]] = {}
	padron_sin_actividad: set[str] = set()
	if not filtro_actividad:
		con_actividad = set(inscripciones_por_socio)
		padron_sin_actividad = set(
			frappe.get_all(SOCIO_DOCTYPE, filters={"estado": ["!=", "Baja"]}, pluck="name")
		) - con_actividad
		for socio_name in sorted(socios_con_deuda & padron_sin_actividad):
			por_item = _deuda_por_item_en_rango(socio_name, desde, hasta)
			cuota = sum(monto for code, monto in por_item.items() if code in cuota_codes)
			if cuota > _TOLERANCIA_DEUDA:
				sin_actividad_socios[socio_name] = {"cuota": cuota, "arancel": 0.0}

	if not buckets and not multi_socios and not sin_actividad_socios:
		return []

	def _padron(*parts: str) -> set[str]:
		"""Socios activos cuyo key coincide con el prefijo (actividad [, grupo [, equipo]])."""
		out: set[str] = set()
		n = len(parts)
		for key, socios in universo.items():
			if key[:n] == parts:
				out |= socios
		return out

	def _deudores_de(socios_por_key: list[dict[str, dict[str, float]]]) -> dict[str, dict[str, float]]:
		"""Une socios de varios buckets sumando sus montos."""
		out: dict[str, dict[str, float]] = {}
		for socios in socios_por_key:
			for socio_name, montos in socios.items():
				_sumar_deuda(out.setdefault(socio_name, {}), montos["cuota"], montos["arancel"])
		return out

	tree: dict[str, dict[str, dict[str, dict[str, dict[str, float]]]]] = {}
	for (actividad, grupo, equipo), socios in buckets.items():
		tree.setdefault(actividad, {}).setdefault(grupo, {})[equipo] = socios

	all_socio_names: set[str] = set(multi_socios) | set(sin_actividad_socios)
	for socios in buckets.values():
		all_socio_names.update(socios.keys())
	nombres = _nombres_socios(all_socio_names)

	def _orden_socios(socios: dict[str, Any]) -> list[str]:
		return sorted(socios, key=lambda n: (nombres.get(n) or n).lower())

	body: list[dict[str, Any]] = []
	for actividad in sorted(tree):
		act_socios = _deudores_de(
			[socios for grupos in tree[actividad].values() for socios in grupos.values()]
		)
		cuota, arancel = _totales_socios(act_socios)
		body.append(
			_fila_deuda_actividad(
				_("Subtotal {0}").format(_titulo_doc("Actividad", actividad) or actividad),
				1,
				cuota,
				arancel,
				_fmt_socios_deudores(len(act_socios), len(_padron(actividad))),
				actividad=actividad,
			)
		)
		for grupo in sorted(tree[actividad]):
			grupo_socios = _deudores_de(list(tree[actividad][grupo].values()))
			cuota, arancel = _totales_socios(grupo_socios)
			grupo_label = _titulo_doc("Grupo Actividad", grupo) if grupo else _("Sin grupo / tira")
			body.append(
				_fila_deuda_actividad(
					_("Subtotal {0}").format(grupo_label),
					2,
					cuota,
					arancel,
					_fmt_socios_deudores(len(grupo_socios), len(_padron(actividad, grupo))),
					actividad=actividad,
					grupo=grupo,
				)
			)
			for equipo in sorted(tree[actividad][grupo]):
				socios = tree[actividad][grupo][equipo]
				# Sin equipo/categoría: omitir fila placeholder; socios cuelgan del grupo (indent 3).
				socio_indent = 3
				if equipo:
					cuota, arancel = _totales_socios(socios)
					body.append(
						_fila_deuda_actividad(
							_titulo_doc("Equipo Actividad", equipo),
							3,
							cuota,
							arancel,
							_fmt_socios_deudores(len(socios), len(_padron(actividad, grupo, equipo))),
							actividad=actividad,
							grupo=grupo,
							equipo=equipo,
						)
					)
					socio_indent = 4
				for socio_name in _orden_socios(socios):
					body.append(
						_fila_deuda_actividad(
							nombres.get(socio_name) or socio_name,
							socio_indent,
							socios[socio_name]["cuota"],
							socios[socio_name]["arancel"],
							"1",
							socio=socio_name,
							actividad=actividad,
							grupo=grupo,
							equipo=equipo,
						)
					)

	for etiqueta, socios, padron in (
		(_("Multiactividad"), multi_socios, len(multi_padron)),
		(_("Sin actividad"), sin_actividad_socios, 0),
	):
		if not socios:
			continue
		cuota, arancel = _totales_socios(socios)
		body.append(_fila_deuda_actividad(etiqueta, 1, cuota, arancel, _fmt_socios_deudores(len(socios), padron)))
		for socio_name in _orden_socios(socios):
			body.append(
				_fila_deuda_actividad(
					nombres.get(socio_name) or socio_name,
					2,
					socios[socio_name]["cuota"],
					socios[socio_name]["arancel"],
					"1",
					socio=socio_name,
					actividades=", ".join(
						_titulo_doc("Actividad", act) or act for act in multi_actividades.get(socio_name, [])
					),
				)
			)

	todos = _deudores_de([*buckets.values(), multi_socios, sin_actividad_socios])
	cuota, arancel = _totales_socios(todos)
	padron_total = _padron() | multi_padron | padron_sin_actividad
	total = _fila_deuda_actividad(
		_("Total"), 0, cuota, arancel, _fmt_socios_deudores(len(todos), len(padron_total))
	)
	return [total, *body]


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
