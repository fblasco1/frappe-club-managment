"""Mora al cobro: tramos 1.er / 2.º vencimiento del período.

Spec: `club_management/specs/recargos_mora_dos_tramos.md`

- Hasta 1.er venc. (día 10 del mes del período): sin mora
- Tras 1.er y hasta 2.º (default día 20): +10 %
- Tras 2.º venc.: valor del mes de pago × 1,15 (10 % + 5 %)
"""

from __future__ import annotations

import calendar
import re
from datetime import date
from typing import Any, Literal

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	_default_company,
	erpnext_cobranza_disponible,
	get_club_settings,
	resolve_cost_center_item,
	resolve_cuota_social,
	sync_saldo_deuda_socio,
)
from club_management.members.services.cobranza_recargo import RECARGO_SUFFIX

MORA_SUFFIX = "-MORA"
_PERIODO_RE = re.compile(r"^(\d{2})/(\d{4})$")

TramoMora = Literal["ninguno", "post_primer", "post_segundo"]


def periodo_es_ajuste_mora(periodo: str | None) -> bool:
	return bool(periodo) and str(periodo).endswith(MORA_SUFFIX)


def periodo_es_recargo_legado(periodo: str | None) -> bool:
	return bool(periodo) and str(periodo).endswith(RECARGO_SUFFIX)


def periodo_mora(periodo_cobro: str) -> str:
	return f"{periodo_cobro}{MORA_SUFFIX}"


def parse_periodo_cobro(periodo: str | None) -> date | None:
	"""`MM/YYYY` → primer día del mes. Ignora sufijos -MORA / -REC."""
	raw = (periodo or "").strip()
	if not raw or raw.endswith(MORA_SUFFIX) or raw.endswith(RECARGO_SUFFIX):
		return None
	match = _PERIODO_RE.match(raw)
	if not match:
		return None
	month = int(match.group(1))
	year = int(match.group(2))
	if not 1 <= month <= 12:
		return None
	return date(year, month, 1)


def meses_vencidos_entre(periodo_cobro: str, posting_date: str | date) -> int:
	inicio = parse_periodo_cobro(periodo_cobro)
	if not inicio:
		return 0
	pago = getdate(posting_date)
	delta = (pago.year - inicio.year) * 12 + (pago.month - inicio.month)
	return max(0, delta)


def _segundo_vencimiento_dia(inicio: date, dia_segundo_vencimiento: str | None) -> date:
	ultimo = calendar.monthrange(inicio.year, inicio.month)[1]
	raw = (dia_segundo_vencimiento or "20").strip()
	if raw == "Ultimo dia del mes":
		return date(inicio.year, inicio.month, ultimo)
	try:
		dia = int(raw)
	except ValueError:
		dia = 20
	return date(inicio.year, inicio.month, min(max(1, dia), ultimo))


def fechas_vencimiento_periodo(
	periodo_cobro: str,
	*,
	dia_primer_vencimiento: int = 10,
	dia_segundo_vencimiento: str | None = "20",
) -> tuple[date, date] | None:
	"""1.er y 2.º vencimiento del mes del período adeudado."""
	inicio = parse_periodo_cobro(periodo_cobro)
	if not inicio:
		return None
	ultimo = calendar.monthrange(inicio.year, inicio.month)[1]
	dia_v1 = min(max(1, int(dia_primer_vencimiento or 10)), ultimo)
	primer = date(inicio.year, inicio.month, dia_v1)
	segundo = _segundo_vencimiento_dia(inicio, dia_segundo_vencimiento)
	if segundo < primer:
		segundo = date(inicio.year, inicio.month, ultimo)
	return primer, segundo


def resolver_tramo_mora(
	periodo_cobro: str,
	posting_date: str | date,
	*,
	dia_primer_vencimiento: int = 10,
	dia_segundo_vencimiento: str | None = "20",
) -> TramoMora:
	fechas = fechas_vencimiento_periodo(
		periodo_cobro,
		dia_primer_vencimiento=dia_primer_vencimiento,
		dia_segundo_vencimiento=dia_segundo_vencimiento,
	)
	if not fechas:
		return "ninguno"
	primer, segundo = fechas
	pago = getdate(posting_date)
	if pago <= primer:
		return "ninguno"
	if pago <= segundo:
		return "post_primer"
	return "post_segundo"


def calcular_monto_exigido_mora(
	*,
	valor_actual: float,
	tramo: TramoMora,
	pct_post_primer: float = 10.0,
	pct_extra_segundo: float = 5.0,
	# Compat: firmas antiguas ignoradas si se pasa tramo explícito vía kwargs legacy
	meses_vencidos: int | None = None,
	paga_despues_dia_vencimiento: bool | None = None,
	pct_mes_vencido: float | None = None,
	pct_post_vencimiento: float | None = None,
) -> float:
	"""Aplica % según tramo. Post 2.º = 10 % + 5 % sobre valor del mes de pago."""
	base = flt(valor_actual)
	if base <= 0:
		return 0.0

	# Compatibilidad con llamadas legacy (tests viejos / código intermedio).
	if meses_vencidos is not None or paga_despues_dia_vencimiento is not None:
		n = max(0, int(meses_vencidos or 0))
		despues = bool(paga_despues_dia_vencimiento)
		if n == 0 and not despues:
			tramo = "ninguno"
		elif n == 0 and despues:
			tramo = "post_primer"
		else:
			tramo = "post_segundo"
		if pct_post_vencimiento is not None:
			pct_post_primer = flt(pct_post_vencimiento)
		if pct_mes_vencido is not None:
			pct_extra_segundo = flt(pct_mes_vencido)

	factor = 1.0
	if tramo == "post_primer":
		factor += flt(pct_post_primer) / 100.0
	elif tramo == "post_segundo":
		factor += flt(pct_post_primer) / 100.0
		factor += flt(pct_extra_segundo) / 100.0
	return flt(base * factor, 2)


def texto_composicion_mora(
	*,
	valor_actual: float,
	tramo: TramoMora,
	pct_post_primer: float,
	pct_extra_segundo: float,
	monto_exigido: float,
	# Compat legacy
	meses_vencidos: int | None = None,
	paga_despues: bool | None = None,
	pct_mes: float | None = None,
	pct_dia: float | None = None,
) -> str:
	"""Ej.: «12.000 × (1 + 10% + 5%) = 13.800»."""
	if meses_vencidos is not None or paga_despues is not None:
		n = max(0, int(meses_vencidos or 0))
		despues = bool(paga_despues)
		if n == 0 and not despues:
			tramo = "ninguno"
		elif n == 0 and despues:
			tramo = "post_primer"
		else:
			tramo = "post_segundo"
		if pct_dia is not None:
			pct_post_primer = flt(pct_dia)
		if pct_mes is not None:
			pct_extra_segundo = flt(pct_mes)

	partes = ["1"]
	if tramo == "post_primer":
		partes.append(f"{flt(pct_post_primer):g}%")
	elif tramo == "post_segundo":
		partes.append(f"{flt(pct_post_primer):g}%")
		partes.append(f"{flt(pct_extra_segundo):g}%")
	factor_txt = " + ".join(partes) if len(partes) > 1 else "1"
	return _("{0} × ({1}) = {2}").format(
		f"{flt(valor_actual):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
		factor_txt,
		f"{flt(monto_exigido):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
	)



def _remarks_mora(invoice_origen: str) -> str:
	return _("Mora al cobro {0}").format(invoice_origen)


def resolve_valor_actual_linea(
	*,
	item_code: str,
	qty: float,
	rate_facturado: float,
	socio_name: str,
	item_cuota: str | None,
	monto_cuota: float,
) -> float:
	"""Valor vigente de una línea (qty × rate vigente)."""
	q = flt(qty) or 1.0
	code = (item_code or "").strip()
	if code and item_cuota and code == item_cuota:
		return flt(monto_cuota) * q
	if code and frappe.db.exists("Item", code):
		rate = flt(frappe.db.get_value("Item", code, "standard_rate") or 0)
		if rate > 0:
			return rate * q
	return flt(rate_facturado) * q


def resolve_valor_actual_factura(invoice_name: str, socio_name: str) -> float:
	"""Suma del precio vigente de **todas** las líneas de la SI.

	Spec: ``recargos_mora_dos_tramos.md`` (factura multi-línea).
	"""
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	monto_cuota, item_cuota = resolve_cuota_social(socio_name)
	total = 0.0
	for row in invoice.get("items") or []:
		total += resolve_valor_actual_linea(
			item_code=row.item_code or "",
			qty=flt(row.qty),
			rate_facturado=flt(row.rate),
			socio_name=socio_name,
			item_cuota=item_cuota,
			monto_cuota=flt(monto_cuota),
		)
	if total > 0:
		return flt(total, 2)
	return flt(invoice.outstanding_amount)


def monto_exigido_con_piso(
	*,
	valor_actual: float,
	outstanding_factura: float,
	tramo: TramoMora,
	pct_post_primer: float,
	pct_extra_segundo: float,
) -> float:
	"""Aplica % sobre valor vigente; no baja del outstanding de la SI × mismo factor.

	El piso usa solo el outstanding de la factura origen (sin SI de mora ya creadas),
	para no recomponer mora sobre mora.
	"""
	desde_valor = calcular_monto_exigido_mora(
		valor_actual=valor_actual,
		tramo=tramo,
		pct_post_primer=pct_post_primer,
		pct_extra_segundo=pct_extra_segundo,
	)
	desde_out = calcular_monto_exigido_mora(
		valor_actual=outstanding_factura,
		tramo=tramo,
		pct_post_primer=pct_post_primer,
		pct_extra_segundo=pct_extra_segundo,
	)
	return flt(max(desde_valor, desde_out), 2)


def _ajustes_mora_pendientes(socio_name: str, invoice_origen: str) -> list[dict[str, Any]]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"outstanding_amount": [">", 0],
			"remarks": ["like", f"%{_remarks_mora(invoice_origen)}%"],
		},
		fields=["name", "outstanding_amount", "grand_total"],
	)
	# remarks like is fragile with translation; also match English-free key
	if not rows:
		rows = frappe.get_all(
			SALES_INVOICE_DOCTYPE,
			filters={
				campo_socio: socio_name,
				"docstatus": 1,
				"outstanding_amount": [">", 0],
				"remarks": ["like", f"%Mora al cobro {invoice_origen}%"],
			},
			fields=["name", "outstanding_amount", "grand_total"],
		)
	return rows


def _outstanding_grupo(invoice_name: str, socio_name: str) -> float:
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	total = flt(invoice.outstanding_amount)
	for row in _ajustes_mora_pendientes(socio_name, invoice_name):
		total += flt(row.outstanding_amount)
	return flt(total, 2)


def _periodo_base(periodo: str | None) -> str:
	raw = (periodo or "").strip()
	for suffix in (MORA_SUFFIX, RECARGO_SUFFIX):
		if raw.endswith(suffix):
			return raw[: -len(suffix)]
	return raw


def _periodo_sort_key(periodo: str | None) -> tuple:
	base = _periodo_base(periodo)
	parsed = parse_periodo_cobro(base)
	if not parsed:
		return (9999, 99, periodo or "")
	return (parsed.year, parsed.month, periodo or "")


def calcular_detalle_mora_factura(
	invoice_name: str,
	*,
	posting_date: str | date | None = None,
) -> dict[str, Any]:
	"""Calcula mora al cobro sin crear facturas (para preview Desk)."""
	settings = get_club_settings()
	ref = getdate(posting_date or today())
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	socio_name = invoice.get(campo_socio) if campo_socio else None
	periodo = (invoice.get(campo_periodo) if campo_periodo else None) or ""
	outstanding = flt(invoice.outstanding_amount)

	result: dict[str, Any] = {
		"invoice": invoice_name,
		"periodo": periodo,
		"concepto": "",
		"valor_actual": outstanding,
		"meses_vencidos": 0,
		"tramo": "ninguno",
		"paga_despues_dia_vencimiento": False,
		"pct_mes_vencido": flt(settings.recargo_mes_vencido_pct if settings.recargo_mes_vencido_pct is not None else 5),
		"pct_post_vencimiento": flt(
			settings.recargo_post_vencimiento_pct if settings.recargo_post_vencimiento_pct is not None else 10
		),
		"outstanding": outstanding,
		"outstanding_grupo": outstanding,
		"monto_exigido": outstanding,
		"monto_ajuste": 0.0,
		"aplica_mora": False,
		"composicion": "",
	}
	if invoice.get("items"):
		result["concepto"] = (invoice.items[0].description or invoice.items[0].item_code or "").strip()

	if not socio_name or not periodo:
		return result
	if periodo_es_ajuste_mora(periodo) or periodo_es_recargo_legado(periodo):
		return result

	dia_v1 = int(settings.dia_primer_vencimiento or 10)
	dia_v2 = settings.dia_segundo_vencimiento or "20"
	pct_extra = result["pct_mes_vencido"]
	pct_post = result["pct_post_vencimiento"]
	outstanding_grupo = _outstanding_grupo(invoice_name, socio_name)
	tramo = resolver_tramo_mora(
		periodo,
		ref,
		dia_primer_vencimiento=dia_v1,
		dia_segundo_vencimiento=dia_v2,
	)
	result["outstanding_grupo"] = outstanding_grupo
	result["meses_vencidos"] = meses_vencidos_entre(periodo, ref)
	result["tramo"] = tramo
	result["paga_despues_dia_vencimiento"] = tramo != "ninguno"

	if tramo == "ninguno":
		result["monto_exigido"] = outstanding_grupo
		return result

	valor_actual = resolve_valor_actual_factura(invoice_name, socio_name)
	monto_exigido = monto_exigido_con_piso(
		valor_actual=valor_actual,
		outstanding_factura=outstanding,
		tramo=tramo,
		pct_post_primer=pct_post,
		pct_extra_segundo=pct_extra,
	)
	ajuste = flt(monto_exigido - outstanding_grupo, 2)
	result.update(
		{
			"valor_actual": valor_actual,
			"monto_exigido": monto_exigido,
			"monto_ajuste": max(0.0, ajuste),
			"aplica_mora": ajuste > 0.005,
			"composicion": texto_composicion_mora(
				valor_actual=max(flt(valor_actual), flt(outstanding)),
				tramo=tramo,
				pct_post_primer=pct_post,
				pct_extra_segundo=pct_extra,
				monto_exigido=monto_exigido,
			),
		}
	)
	return result


def previsualizar_cobro_con_mora(
	socio_name: str,
	sales_invoices: list[str],
	*,
	posting_date: str | date | None = None,
) -> dict[str, Any]:
	"""Preview de total con mora **sin** crear SI de ajuste."""
	from club_management.members.services.socio_operaciones_secretaria import (
		ensure_secretaria_operacion_access,
	)

	ensure_secretaria_operacion_access()
	ref = getdate(posting_date or today())
	detalle: list[dict[str, Any]] = []
	total = 0.0
	ajustes_estimados = 0.0
	seen: set[str] = set()
	for name in sales_invoices:
		invoice_name = str(name).strip()
		if not invoice_name or invoice_name in seen:
			continue
		seen.add(invoice_name)
		info = calcular_detalle_mora_factura(invoice_name, posting_date=ref)
		detalle.append(info)
		total += flt(info["monto_exigido"])
		ajustes_estimados += flt(info["monto_ajuste"])

	detalle.sort(key=lambda r: (_periodo_sort_key(r.get("periodo")), r.get("invoice") or ""))
	return {
		"sales_invoices": list(seen),
		"detalle": detalle,
		"total_exigido": flt(total, 2),
		"total_ajustes": flt(ajustes_estimados, 2),
		"posting_date": str(ref),
		"aplica_mora": ajustes_estimados > 0.005,
	}


def _leaf_cost_center(preferred: str | None, company: str) -> str | None:
	"""Devuelve un centro de costo hoja usable en transacciones."""
	candidates: list[str] = []
	if preferred:
		candidates.append(preferred)
	abbr = frappe.get_cached_value("Company", company, "abbr")
	if abbr:
		candidates.append(f"Administración - {abbr}")
		candidates.append(f"Cuotas Sociales - {abbr}")
	for name in candidates:
		if name and frappe.db.exists("Cost Center", name):
			if not int(frappe.db.get_value("Cost Center", name, "is_group") or 0):
				return name
	return frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 0},
		"name",
	)


def asegurar_ajuste_mora_factura(
	invoice_name: str,
	*,
	posting_date: str | date | None = None,
) -> dict[str, Any]:
	"""Crea SI de ajuste si el monto exigido supera el outstanding del grupo.

	Devuelve dict con keys: invoice, ajuste (opcional), monto_exigido, outstanding_grupo.
	"""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	settings = get_club_settings()
	ref = getdate(posting_date or today())
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	campo_periodo = _campo_periodo_cobro()
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	socio_name = invoice.get(campo_socio) if campo_socio else None
	periodo = (invoice.get(campo_periodo) if campo_periodo else None) or ""

	result: dict[str, Any] = {
		"invoice": invoice_name,
		"ajuste": None,
		"monto_exigido": flt(invoice.outstanding_amount),
		"outstanding_grupo": flt(invoice.outstanding_amount),
	}

	if not socio_name or not periodo:
		return result
	if periodo_es_ajuste_mora(periodo) or periodo_es_recargo_legado(periodo):
		return result

	dia_v1 = int(settings.dia_primer_vencimiento or 10)
	dia_v2 = settings.dia_segundo_vencimiento or "20"
	pct_extra = flt(settings.recargo_mes_vencido_pct if settings.recargo_mes_vencido_pct is not None else 5)
	pct_post = flt(
		settings.recargo_post_vencimiento_pct if settings.recargo_post_vencimiento_pct is not None else 10
	)
	tramo = resolver_tramo_mora(
		periodo,
		ref,
		dia_primer_vencimiento=dia_v1,
		dia_segundo_vencimiento=dia_v2,
	)

	if tramo == "ninguno":
		outstanding = _outstanding_grupo(invoice_name, socio_name)
		result["outstanding_grupo"] = outstanding
		result["monto_exigido"] = outstanding
		return result

	outstanding_grupo = _outstanding_grupo(invoice_name, socio_name)
	valor_actual = resolve_valor_actual_factura(invoice_name, socio_name)
	monto_exigido = monto_exigido_con_piso(
		valor_actual=valor_actual,
		outstanding_factura=flt(invoice.outstanding_amount),
		tramo=tramo,
		pct_post_primer=pct_post,
		pct_extra_segundo=pct_extra,
	)
	result["monto_exigido"] = monto_exigido
	result["outstanding_grupo"] = outstanding_grupo

	diferencia = flt(monto_exigido - outstanding_grupo, 2)
	if diferencia <= 0.005:
		return result

	item_recargo = (settings.item_recargo_mora or "").strip()
	if not item_recargo or not frappe.db.exists("Item", item_recargo):
		frappe.throw(
			_(
				"Hay mora a aplicar sobre {0} pero falta configurar el item de mora "
				"(Club Settings > item_recargo_mora)."
			).format(invoice_name),
			frappe.ValidationError,
		)

	item_line: dict[str, Any] = {
		"item_code": item_recargo,
		"qty": 1,
		"rate": diferencia,
		"description": _("Mora {0}: {1}").format(
			periodo,
			texto_composicion_mora(
				valor_actual=max(flt(valor_actual), flt(invoice.outstanding_amount)),
				tramo=tramo,
				pct_post_primer=pct_post,
				pct_extra_segundo=pct_extra,
				monto_exigido=monto_exigido,
			),
		),
	}
	company = invoice.company or _default_company()
	preferred_cc = None
	if invoice.get("items"):
		preferred_cc = invoice.items[0].get("cost_center")
	if not preferred_cc:
		preferred_cc = resolve_cost_center_item(item_recargo, company)
	if not preferred_cc and invoice.get("items"):
		origen_item = (invoice.items[0].item_code or "").strip()
		if origen_item:
			preferred_cc = resolve_cost_center_item(origen_item, company)
	cost_center = _leaf_cost_center(preferred_cc, company)
	if cost_center:
		item_line["cost_center"] = cost_center

	# Asiento del ajuste: fecha de hoy (la fórmula usa `ref` = fecha de cobro).
	posting_si = getdate(today())
	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": invoice.customer,
		"company": company,
		"posting_date": posting_si,
		"due_date": posting_si,
		"disable_rounded_total": 1,
		"remarks": _remarks_mora(invoice_name),
		"items": [item_line],
	}
	if cost_center:
		payload["cost_center"] = cost_center
	if campo_socio:
		payload[campo_socio] = socio_name
	if campo_periodo:
		payload[campo_periodo] = periodo_mora(periodo)

	ajuste = frappe.get_doc(payload)
	if cost_center:
		ajuste.cost_center = cost_center
		for row in ajuste.items:
			row.cost_center = cost_center
	ajuste.taxes_and_charges = ""
	ajuste.set("taxes", [])
	ajuste.flags.ignore_pricing_rule = True
	ajuste.insert(ignore_permissions=True)
	# Recalcular sin impuestos / redondeos que desvíen el monto de mora.
	ajuste.taxes_and_charges = ""
	ajuste.set("taxes", [])
	ajuste.disable_rounded_total = 1
	for row in ajuste.items:
		row.rate = diferencia
		row.amount = diferencia
	ajuste.calculate_taxes_and_totals()
	ajuste.save(ignore_permissions=True)
	ajuste.submit()
	sync_saldo_deuda_socio(socio_name)
	result["ajuste"] = ajuste.name
	result["outstanding_grupo"] = flt(outstanding_grupo + flt(ajuste.outstanding_amount), 2)
	return result


def preparar_facturas_cobro_con_mora(
	socio_name: str,
	sales_invoices: list[str],
	*,
	posting_date: str | date | None = None,
) -> dict[str, Any]:
	"""Asegura ajustes de mora y devuelve lista expandida + total a cobrar."""
	ref = getdate(posting_date or today())
	expanded: list[str] = []
	ajustes: list[str] = []
	detalle: list[dict[str, Any]] = []
	total = 0.0

	seen: set[str] = set()
	for name in sales_invoices:
		invoice_name = str(name).strip()
		if not invoice_name or invoice_name in seen:
			continue
		seen.add(invoice_name)

		info = asegurar_ajuste_mora_factura(invoice_name, posting_date=ref)
		if invoice_name not in expanded:
			expanded.append(invoice_name)
		if info.get("ajuste"):
			ajustes.append(info["ajuste"])
			expanded.append(info["ajuste"])

		# Incluir ajustes previos aún pendientes
		for row in _ajustes_mora_pendientes(socio_name, invoice_name):
			if row.name not in expanded:
				expanded.append(row.name)
				if row.name not in ajustes:
					ajustes.append(row.name)

		detalle.append(info)
		total += flt(info["monto_exigido"])

	# Total a cobrar = outstanding real de la lista expandida (debe igualar la fórmula).
	total_outstanding = 0.0
	campo = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	for inv_name in expanded:
		inv = frappe.get_doc(SALES_INVOICE_DOCTYPE, inv_name)
		if campo and inv.get(campo) != socio_name:
			frappe.throw(_("La factura {0} no pertenece a este socio.").format(inv_name), frappe.ValidationError)
		total_outstanding += flt(inv.outstanding_amount)

	return {
		"sales_invoices": expanded,
		"ajustes": ajustes,
		"total_exigido": flt(total_outstanding, 2),
		"detalle": detalle,
		"posting_date": str(ref),
	}
