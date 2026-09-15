"""Bonificación de arancel al cobro (masiva / individual).

Spec: ``bonificacion_arancel_al_cobro.md``.
"""

from __future__ import annotations

from typing import Any

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

BONIFICACION_DOCTYPE = "Bonificacion Arancel"
BONIF_REMARKS_PREFIX = "Bonificacion arancel "


def _remarks_bonificacion(invoice_origen: str) -> str:
	return f"{BONIF_REMARKS_PREFIX}{invoice_origen}"


def monto_arancel_en_factura(invoice_name: str, socio_name: str) -> float:
	"""Suma de líneas de arancel (excluye cuota social e ítems de ajuste)."""
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	_, item_cuota = resolve_cuota_social(socio_name)
	settings = get_club_settings()
	excluidos = {
		(item_cuota or "").strip(),
		(settings.item_recargo_mora or "").strip(),
		(settings.item_bonificacion_arancel or "").strip(),
	}
	excluidos.discard("")
	total = 0.0
	for row in invoice.get("items") or []:
		code = (row.item_code or "").strip()
		if code in excluidos:
			continue
		desc = (row.description or "").lower()
		# Líneas de mora/bonif residuales por descripción
		if "mora " in desc or desc.startswith("mora") or "bonificacion" in desc:
			continue
		total += flt(row.amount)
	return flt(total, 2)


def _inscripciones_socio(socio_name: str) -> list[dict[str, Any]]:
	if not frappe.db.exists("DocType", "Inscripcion Actividad"):
		return []
	return frappe.get_all(
		"Inscripcion Actividad",
		filters={"socio": socio_name, "estado": "Activa"},
		fields=["name", "actividad", "grupo_actividad", "equipo_actividad"],
	)


def _bonificacion_matchea_inscripcion(bonif: dict[str, Any], insc: dict[str, Any]) -> bool:
	"""Más específico gana: equipo > grupo > actividad."""
	if bonif.get("equipo_actividad"):
		return bonif["equipo_actividad"] == insc.get("equipo_actividad")
	if bonif.get("grupo_actividad"):
		return bonif["grupo_actividad"] == insc.get("grupo_actividad")
	if bonif.get("actividad"):
		return bonif["actividad"] == insc.get("actividad")
	# Individual sin alcance de actividad: aplica si hay arancel
	return bool(bonif.get("socio"))


def list_bonificaciones_aplicables(
	socio_name: str,
	periodo_cobro: str,
) -> list[dict[str, Any]]:
	"""Bonificaciones Activas del período que aplican al socio (individual o masiva)."""
	if not frappe.db.exists("DocType", BONIFICACION_DOCTYPE):
		return []
	periodo = (periodo_cobro or "").strip()
	if not periodo:
		return []

	rows = frappe.get_all(
		BONIFICACION_DOCTYPE,
		filters={"periodo_cobro": periodo, "estado": "Activa"},
		fields=[
			"name",
			"socio",
			"actividad",
			"grupo_actividad",
			"equipo_actividad",
			"tipo_descuento",
			"valor",
			"motivo",
		],
	)
	inscripciones = _inscripciones_socio(socio_name)
	aplicables: list[dict[str, Any]] = []
	for row in rows:
		if row.socio:
			if row.socio == socio_name:
				aplicables.append(row)
			continue
		# Masiva: al menos una inscripción encaja
		if any(_bonificacion_matchea_inscripcion(row, insc) for insc in inscripciones):
			aplicables.append(row)
	return aplicables


def calcular_monto_bonificacion(
	*,
	monto_arancel: float,
	bonificaciones: list[dict[str, Any]],
) -> dict[str, Any]:
	"""Suma descuentos con tope = monto_arancel."""
	tope = flt(monto_arancel)
	if tope <= 0 or not bonificaciones:
		return {
			"monto_bonificacion": 0.0,
			"detalle": [],
			"motivos": [],
		}

	acum = 0.0
	detalle: list[dict[str, Any]] = []
	motivos: list[str] = []
	for bon in bonificaciones:
		if acum >= tope - 0.005:
			break
		valor = flt(bon.get("valor"))
		if bon.get("tipo_descuento") == "Porcentaje":
			parte = flt(tope * valor / 100.0, 2)
		else:
			parte = flt(valor, 2)
		parte = min(parte, flt(tope - acum, 2))
		if parte <= 0:
			continue
		acum = flt(acum + parte, 2)
		detalle.append(
			{
				"bonificacion": bon.get("name"),
				"monto": parte,
				"motivo": bon.get("motivo") or "",
				"tipo_descuento": bon.get("tipo_descuento"),
				"valor": valor,
			}
		)
		if bon.get("motivo"):
			motivos.append(str(bon["motivo"]))

	return {
		"monto_bonificacion": flt(acum, 2),
		"detalle": detalle,
		"motivos": motivos,
	}


def calcular_bonificacion_factura(invoice_name: str, socio_name: str) -> dict[str, Any]:
	"""Monto de bonificación aplicable a una SI (sin crear CN)."""
	campo_periodo = _campo_periodo_cobro()
	periodo = ""
	if campo_periodo:
		periodo = (frappe.db.get_value(SALES_INVOICE_DOCTYPE, invoice_name, campo_periodo) or "").strip()
	arancel = monto_arancel_en_factura(invoice_name, socio_name)
	bons = list_bonificaciones_aplicables(socio_name, periodo)
	calc = calcular_monto_bonificacion(monto_arancel=arancel, bonificaciones=bons)
	return {
		"invoice": invoice_name,
		"periodo": periodo,
		"monto_arancel": arancel,
		**calc,
	}


def _credit_notes_pendientes(socio_name: str, invoice_origen: str) -> list[dict[str, Any]]:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	return frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"is_return": 1,
			"return_against": invoice_origen,
			"remarks": ["like", f"%{_remarks_bonificacion(invoice_origen)}%"],
		},
		fields=["name", "grand_total", "outstanding_amount"],
	)


def _monto_cn_ya_aplicado(socio_name: str, invoice_origen: str) -> float:
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return 0.0
	total = 0.0
	for name in frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters={
			campo_socio: socio_name,
			"docstatus": 1,
			"is_return": 1,
			"return_against": invoice_origen,
			"remarks": ["like", f"%{_remarks_bonificacion(invoice_origen)}%"],
		},
		pluck="name",
	):
		total += abs(flt(frappe.db.get_value(SALES_INVOICE_DOCTYPE, name, "grand_total")))
	return flt(total, 2)


def asegurar_credit_note_bonificacion(
	invoice_name: str,
	*,
	monto: float,
	motivo: str = "",
	posting_date: str | None = None,
) -> dict[str, Any]:
	"""Crea CN idempotente por el monto de bonificación pendiente."""
	if not erpnext_cobranza_disponible():
		frappe.throw(_("ERPNext no está disponible para cobranza."), frappe.ValidationError)

	monto = flt(monto, 2)
	result: dict[str, Any] = {"invoice": invoice_name, "credit_note": None, "monto": monto}
	if monto <= 0.005:
		return result

	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	invoice = frappe.get_doc(SALES_INVOICE_DOCTYPE, invoice_name)
	socio_name = invoice.get(campo_socio) if campo_socio else None
	if not socio_name:
		return result

	ya = _monto_cn_ya_aplicado(socio_name, invoice_name)
	faltante = flt(monto - ya, 2)
	if faltante <= 0.005:
		existentes = _credit_notes_pendientes(socio_name, invoice_name)
		if existentes:
			result["credit_note"] = existentes[0]["name"]
		return result

	settings = get_club_settings()
	item_bonif = (settings.item_bonificacion_arancel or "").strip()
	if not item_bonif or not frappe.db.exists("Item", item_bonif):
		frappe.throw(
			_(
				"Hay bonificación de arancel sobre {0} pero falta configurar "
				"Club Settings > ítem bonificación arancel."
			).format(invoice_name),
			frappe.ValidationError,
		)

	company = invoice.company or _default_company()
	_cuota_monto, item_cuota = resolve_cuota_social(socio_name)
	excluidos = {
		(item_cuota or "").strip(),
		(settings.item_recargo_mora or "").strip(),
		item_bonif,
	}
	excluidos.discard("")

	# CN debe devolver el mismo ítem de la línea de arancel (regla ERPNext return).
	origen_row = None
	for row in invoice.get("items") or []:
		code = (row.item_code or "").strip()
		if code and code not in excluidos and flt(row.amount) > 0:
			origen_row = row
			break
	if not origen_row and invoice.get("items"):
		origen_row = invoice.items[0]

	if not origen_row:
		frappe.throw(_("La factura {0} no tiene líneas para bonificar.").format(invoice_name))

	rate = faltante
	qty = -1.0
	preferred_cc = origen_row.get("cost_center") or resolve_cost_center_item(
		origen_row.item_code, company
	)
	desc = _("Bonificación arancel ({0}): {1}").format(item_bonif, motivo or invoice_name)
	item_line: dict[str, Any] = {
		"item_code": origen_row.item_code,
		"qty": qty,
		"rate": rate,
		"description": desc,
		"sales_invoice_item": origen_row.name,
	}
	if preferred_cc:
		item_line["cost_center"] = preferred_cc

	ref = getdate(posting_date or today())
	posting_cn = ref
	inv_posting = getdate(invoice.posting_date)
	if posting_cn < inv_posting:
		posting_cn = inv_posting
	from frappe.utils import add_to_date, get_datetime, now_datetime

	payload: dict[str, Any] = {
		"doctype": SALES_INVOICE_DOCTYPE,
		"customer": invoice.customer,
		"company": company,
		"is_return": 1,
		"return_against": invoice_name,
		"update_outstanding_for_self": 0,
		"posting_date": posting_cn,
		"due_date": posting_cn,
		"set_posting_time": 1,
		"disable_rounded_total": 1,
		"remarks": _remarks_bonificacion(invoice_name),
		"items": [item_line],
	}
	origen_ts = get_datetime(invoice.get("posting_date"))
	if invoice.meta.has_field("posting_time") and invoice.get("posting_time"):
		try:
			origen_ts = get_datetime(f"{invoice.posting_date} {invoice.posting_time}")
		except Exception:
			origen_ts = get_datetime(invoice.posting_date)
	cn_ts = add_to_date(origen_ts, seconds=5)
	if getdate(cn_ts) == posting_cn:
		payload["posting_time"] = cn_ts.strftime("%H:%M:%S")
	elif posting_cn > inv_posting:
		payload["posting_time"] = "00:00:01"
	else:
		payload["posting_time"] = now_datetime().strftime("%H:%M:%S")
	if campo_socio:
		payload[campo_socio] = socio_name
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo and invoice.get(campo_periodo):
		payload[campo_periodo] = invoice.get(campo_periodo)

	cn = frappe.get_doc(payload)
	if cn.meta.has_field("update_outstanding_for_self"):
		cn.update_outstanding_for_self = 0
	cn.taxes_and_charges = ""
	cn.set("taxes", [])
	cn.flags.ignore_pricing_rule = True
	cn.insert(ignore_permissions=True)
	cn.taxes_and_charges = ""
	cn.set("taxes", [])
	if cn.meta.has_field("update_outstanding_for_self"):
		cn.update_outstanding_for_self = 0
	for row in cn.items:
		row.qty = qty
		row.rate = rate
		row.amount = -faltante
	cn.calculate_taxes_and_totals()
	cn.save(ignore_permissions=True)
	cn.submit()
	# Forzar refresco del outstanding de la SI origen.
	invoice.reload()
	sync_saldo_deuda_socio(socio_name)
	result["credit_note"] = cn.name
	result["monto"] = faltante
	return result
