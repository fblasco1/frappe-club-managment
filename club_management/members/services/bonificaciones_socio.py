"""Bonificaciones activas de un socio y su cancelación desde la ficha (spec bonificaciones_activas_socio.md)."""

from __future__ import annotations

from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate, today

from club_management.members.services.socio_operaciones_secretaria import (
	ensure_secretaria_operacion_access,
)

BECA = "Beca Socio"
RECURRENTE = "Bonificacion Recurrente"
ARANCEL = "Bonificacion Arancel"

ESTADO_CANCELADO: dict[str, str] = {
	BECA: "Cancelada",
	RECURRENTE: "Anulada",
	ARANCEL: "Anulada",
}


def _fmt_fecha(value: Any) -> str:
	return getdate(value).strftime("%d/%m/%Y") if value else ""


def _vigencia(desde: Any, hasta: Any) -> str:
	if desde and hasta:
		return _("{0} al {1}").format(_fmt_fecha(desde), _fmt_fecha(hasta))
	if desde:
		return _("Desde {0}").format(_fmt_fecha(desde))
	return ""


def _descuento(tipo_descuento: str | None, valor: float) -> str:
	if tipo_descuento == "Porcentaje":
		return f"{flt(valor):g}%"
	return fmt_money(flt(valor), precision=0, currency="ARS").replace("ARS", "$").strip()


def _alcance(row: dict[str, Any]) -> str:
	partes = [row.get(f) for f in ("actividad", "grupo_actividad", "equipo_actividad") if row.get(f)]
	return " / ".join(partes) if partes else _("Arancel")


def _becas(socio: str, hoy: date) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		BECA,
		filters={"socio": socio, "estado": "Activa"},
		fields=["name", "tipo_beca", "pct_cuota_social", "pct_arancel", "fecha_desde", "fecha_hasta", "observaciones"],
		order_by="fecha_desde desc",
	)
	result = []
	for row in rows:
		if row.fecha_hasta and getdate(row.fecha_hasta) < hoy:
			continue
		descuentos = []
		if flt(row.pct_cuota_social):
			descuentos.append(_("Cuota {0}%").format(f"{flt(row.pct_cuota_social):g}"))
		if flt(row.pct_arancel):
			descuentos.append(_("Arancel {0}%").format(f"{flt(row.pct_arancel):g}"))
		result.append(
			{
				"doctype": BECA,
				"name": row.name,
				"tipo": _("Beca ({0})").format(row.tipo_beca or ""),
				"descuento": " · ".join(descuentos),
				"alcance": _("Cuota social / Arancel"),
				"vigencia": _vigencia(row.fecha_desde, row.fecha_hasta),
				"motivo": row.observaciones or "",
			}
		)
	return result


def _recurrentes(socio: str, hoy: date) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		RECURRENTE,
		filters={"socio": socio, "estado": "Activa"},
		fields=["name", "tipo_descuento", "valor", "actividad", "grupo_actividad", "fecha_desde", "fecha_hasta", "motivo"],
		order_by="fecha_desde desc",
	)
	return [
		{
			"doctype": RECURRENTE,
			"name": row.name,
			"tipo": _("Bonificación recurrente"),
			"descuento": _descuento(row.tipo_descuento, row.valor),
			"alcance": _alcance(row),
			"vigencia": _vigencia(row.fecha_desde, row.fecha_hasta),
			"motivo": row.motivo or "",
		}
		for row in rows
		if not row.fecha_hasta or getdate(row.fecha_hasta) >= hoy
	]


def _aranceles(socio: str) -> list[dict[str, Any]]:
	rows = frappe.get_all(
		ARANCEL,
		filters={"socio": socio, "estado": "Activa"},
		fields=["name", "periodo_cobro", "tipo_descuento", "valor", "actividad", "grupo_actividad", "equipo_actividad", "motivo"],
		order_by="creation desc",
	)
	return [
		{
			"doctype": ARANCEL,
			"name": row.name,
			"tipo": _("Bonificación de arancel"),
			"descuento": _descuento(row.tipo_descuento, row.valor),
			"alcance": _alcance(row),
			"vigencia": row.periodo_cobro or "",
			"motivo": row.motivo or "",
		}
		for row in rows
	]


def list_bonificaciones_activas(socio: str, *, reference_date: str | date | None = None) -> list[dict[str, Any]]:
	ensure_secretaria_operacion_access()
	if not frappe.db.exists("Socio", socio):
		frappe.throw(_("Socio no encontrado"), frappe.DoesNotExistError)
	hoy = getdate(reference_date or today())
	rows: list[dict[str, Any]] = []
	if frappe.db.exists("DocType", BECA):
		rows += _becas(socio, hoy)
	if frappe.db.exists("DocType", RECURRENTE):
		rows += _recurrentes(socio, hoy)
	if frappe.db.exists("DocType", ARANCEL):
		rows += _aranceles(socio)
	return rows


def cancelar_bonificacion(doctype: str, name: str, socio: str) -> str:
	ensure_secretaria_operacion_access()
	if doctype not in ESTADO_CANCELADO:
		frappe.throw(_("Tipo de bonificación no válido: {0}").format(doctype))
	doc = frappe.get_doc(doctype, name)
	if doc.get("socio") != socio:
		frappe.throw(_("La bonificación {0} no pertenece a este socio.").format(name))
	doc.check_permission("write")
	nuevo = ESTADO_CANCELADO[doctype]
	if doc.estado != nuevo:
		doc.estado = nuevo
		doc.save()
	return nuevo
