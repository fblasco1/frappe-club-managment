"""Reportería PDF de la grilla de ocupación de espacios (08:00–04:00)."""

from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import escape_html, getdate, today

from club_management.spaces.services.ocupacion_dashboard import (
	WINDOW_START_MIN,
	get_ocupacion_dashboard_payload,
)

MAX_DIAS_REPORTE = 31
_SLOT_PX = 16


def ocupacion_pdf_wkhtml_options() -> dict[str, str]:
	"""Opciones wkhtmltopdf: A4 horizontal, sin márgenes (la grilla usa todo el ancho)."""
	return {
		"orientation": "Landscape",
		"page-size": "A4",
		"margin-top": "0mm",
		"margin-bottom": "0mm",
		"margin-left": "0mm",
		"margin-right": "0mm",
	}


def _parse_fechas_list(raw: str | list | None) -> list[date]:
	if raw is None or raw == "":
		return []
	if isinstance(raw, str):
		raw = raw.strip()
		if not raw:
			return []
		try:
			parsed = json.loads(raw)
		except json.JSONDecodeError:
			return [getdate(part.strip()) for part in raw.split(",") if part.strip()]
		raw = parsed
	if not isinstance(raw, (list, tuple)):
		frappe.throw(_("fechas debe ser una lista"), frappe.ValidationError)
	return [getdate(item) for item in raw]


def normalize_fechas_reporte(
	*,
	fecha: str | date | None = None,
	fecha_desde: str | date | None = None,
	fecha_hasta: str | date | None = None,
	fechas: str | list | None = None,
) -> list[date]:
	"""Normaliza `fecha` | `fecha_desde`+`fecha_hasta` | lista `fechas` (máx. 31)."""
	lista = _parse_fechas_list(fechas)
	if lista:
		uniq = sorted({getdate(d) for d in lista})
	elif fecha_desde or fecha_hasta:
		if not fecha_desde or not fecha_hasta:
			frappe.throw(
				_("Indicá fecha_desde y fecha_hasta"),
				frappe.ValidationError,
			)
		inicio = getdate(fecha_desde)
		fin = getdate(fecha_hasta)
		if fin < inicio:
			frappe.throw(
				_("fecha_hasta debe ser mayor o igual a fecha_desde"),
				frappe.ValidationError,
			)
		uniq: list[date] = []
		cur = inicio
		while cur <= fin:
			uniq.append(cur)
			cur = cur + timedelta(days=1)
	else:
		uniq = [getdate(fecha or today())]

	if len(uniq) > MAX_DIAS_REPORTE:
		frappe.throw(
			_("El reporte no puede superar {0} días").format(MAX_DIAS_REPORTE),
			frappe.ValidationError,
		)
	if not uniq:
		frappe.throw(_("Indicá al menos una fecha"), frappe.ValidationError)
	return uniq


def _block_label(bloque: dict[str, Any]) -> str:
	etiqueta = (bloque.get("etiqueta_planilla") or "").strip()
	if etiqueta:
		return etiqueta.replace("\n", " · ")
	parts: list[str] = []
	titulo = (bloque.get("titulo") or "").strip()
	if titulo:
		parts.append(titulo)
	arrendatario = (bloque.get("arrendatario_nombre") or "").strip()
	if arrendatario and arrendatario not in titulo:
		parts.append(arrendatario)
	tipo = (
		bloque.get("categoria") or bloque.get("tipo") or bloque.get("tipo_sesion") or ""
	).strip()
	estado = (bloque.get("estado") or "").strip()
	meta: list[str] = []
	if tipo:
		meta.append(str(tipo))
	if estado in {"Pendiente", "Confirmada"}:
		meta.append(estado)
	label = " — ".join(parts) if parts else _("Ocupado")
	if meta:
		label = f"{label} ({', '.join(meta)})"
	return label


def _blocks_by_espacio(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
	out: dict[str, list[dict[str, Any]]] = {}
	for bloque in payload.get("bloques") or []:
		key = str(bloque.get("espacio") or "")
		out.setdefault(key, []).append(bloque)
	return out


def _render_day_section(payload: dict[str, Any]) -> str:
	fecha = escape_html(str(payload.get("fecha") or ""))
	dia = escape_html(str(payload.get("dia_semana") or ""))
	espacios = payload.get("espacios") or []
	slots = payload.get("slots") or []
	by_esp = _blocks_by_espacio(payload)

	total_h = max(len(slots) * _SLOT_PX, _SLOT_PX)
	time_labels = "".join(
		f"<div class='slot-label' style='height:{_SLOT_PX}px'>{escape_html(s)}</div>"
		for s in slots
	)
	cols_html: list[str] = []
	for esp in espacios:
		name = str(esp.get("name") or "")
		title = escape_html(esp.get("titulo_planilla") or esp.get("titulo") or name)
		bloques_html: list[str] = []
		for b in by_esp.get(name, []):
			inicio_min = int(b.get("inicio_min") or WINDOW_START_MIN)
			fin_min = int(b.get("fin_min") or inicio_min + 30)
			top = max(0.0, (inicio_min - WINDOW_START_MIN) / 30 * _SLOT_PX)
			height = max((fin_min - inicio_min) / 30 * _SLOT_PX, _SLOT_PX * 0.6)
			estado = (b.get("estado") or "").strip()
			cls = "abs-bloque"
			if estado == "Pendiente":
				cls += " pendiente"
			elif estado == "Confirmada":
				cls += " confirmada"
			color = escape_html(str(b.get("color") or "#d0d7de"))
			label = escape_html(_block_label(b))
			bloques_html.append(
				f"<div class='{cls}' style='top:{top:.1f}px;height:{height:.1f}px;"
				f"background:{color}'>{label}</div>"
			)
		cols_html.append(
			f"<div class='col-espacio'>"
			f"<div class='col-head'>{title}</div>"
			f"<div class='col-body' style='height:{total_h}px'>{''.join(bloques_html)}</div>"
			f"</div>"
		)

	return f"""
<section class="dia">
  <h2>Ocupación — {fecha} ({dia})</h2>
  <p class="ventana">Ventana 08:00 – 04:00</p>
  <div class="grilla">
    <div class="col-hora">
      <div class="col-head">HORA</div>
      <div class="col-body" style="height:{total_h}px">{time_labels}</div>
    </div>
    {"".join(cols_html)}
  </div>
</section>
"""


def build_ocupacion_reporte_html_from_payloads(payloads: list[dict[str, Any]]) -> str:
	"""Arma HTML escapado a partir de payloads del dashboard (testeable sin DB)."""
	sections = [_render_day_section(p) for p in payloads]
	leyenda_items: list[str] = []
	if payloads:
		for item in payloads[0].get("leyenda") or []:
			label = escape_html(item.get("label") or "")
			color = escape_html(item.get("color") or "#ccc")
			leyenda_items.append(
				f"<span class='leyenda-item'>"
				f"<span class='swatch' style='background:{color}'></span>{label}</span>"
			)
	leyenda_items.append(
		"<span class='leyenda-item'><span class='swatch pendiente-swatch'></span>"
		f"{escape_html(_('Pendiente (bloqueo)'))}</span>"
	)
	leyenda_items.append(
		"<span class='leyenda-item'><span class='swatch confirmada-swatch'></span>"
		f"{escape_html(_('Confirmada'))}</span>"
	)

	return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>{escape_html(_("Ocupación de espacios"))}</title>
<style>
  @page {{ size: A4 landscape; margin: 0; }}
  .print-format {{
    margin-top: 0mm;
    margin-bottom: 0mm;
    margin-left: 0mm;
    margin-right: 0mm;
    orientation: Landscape;
    page-size: A4;
  }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: DejaVu Sans, sans-serif; font-size: 7pt; color: #222; }}
  .print-format {{ padding: 2mm; box-sizing: border-box; width: 100%; }}
  h1 {{ font-size: 11pt; margin: 0 0 3px; }}
  h2 {{ font-size: 9pt; margin: 6px 0 2px; page-break-after: avoid; }}
  .ventana {{ margin: 0 0 4px; color: #555; font-size: 7pt; }}
  .leyenda {{ margin-bottom: 4px; font-size: 6.5pt; }}
  .leyenda-item {{ display: inline-block; margin-right: 8px; }}
  .swatch {{ display: inline-block; width: 8px; height: 8px; margin-right: 2px;
            vertical-align: middle; border: 1px solid #999; }}
  .pendiente-swatch {{ background: #fff; border-style: dashed; border-color: #e67e22; }}
  .confirmada-swatch {{ background: #fff; border-style: solid; border-color: #27ae60;
                       border-width: 2px; }}
  .dia {{ page-break-inside: avoid; margin-bottom: 8px; page-break-after: always; }}
  .dia:last-child {{ page-break-after: auto; }}
  .grilla {{ display: table; width: 100%; table-layout: fixed; border-collapse: collapse; }}
  .col-hora, .col-espacio {{ display: table-cell; vertical-align: top;
                             border: 1px solid #ccc; overflow: hidden; }}
  .col-hora {{ width: 28px; }}
  .col-head {{ background: #f0f0f0; font-weight: bold; text-align: center;
              padding: 2px 1px; border-bottom: 1px solid #ccc; font-size: 6pt;
              word-break: break-word; line-height: 1.15; }}
  .col-body {{ position: relative; background: repeating-linear-gradient(
                 to bottom, #fafafa 0, #fafafa {_SLOT_PX - 1}px,
                 #e8e8e8 {_SLOT_PX - 1}px, #e8e8e8 {_SLOT_PX}px); }}
  .slot-label {{ font-size: 5.5pt; padding-left: 1px; box-sizing: border-box; }}
  .abs-bloque {{ position: absolute; left: 1px; right: 1px; overflow: hidden;
                 font-size: 5.5pt; line-height: 1.1; padding: 0 1px;
                 border: 1px solid rgba(0,0,0,0.25); border-radius: 1px;
                 box-sizing: border-box; word-break: break-word; }}
  .abs-bloque.pendiente {{ border: 1.5px dashed #e67e22; opacity: 0.92; }}
  .abs-bloque.confirmada {{ border: 2px solid #27ae60; }}
</style>
</head>
<body>
<div class="print-format">
  <h1>{escape_html(_("Reporte de ocupación de espacios"))}</h1>
  <div class="leyenda">{"".join(leyenda_items)}</div>
  {"".join(sections)}
</div>
</body>
</html>
"""


def build_ocupacion_reporte_html(
	*,
	fecha: str | date | None = None,
	fecha_desde: str | date | None = None,
	fecha_hasta: str | date | None = None,
	fechas: str | list | None = None,
) -> str:
	dias = normalize_fechas_reporte(
		fecha=fecha,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		fechas=fechas,
	)
	payloads = [get_ocupacion_dashboard_payload(fecha=d) for d in dias]
	return build_ocupacion_reporte_html_from_payloads(payloads)


def build_ocupacion_reporte_pdf_bytes(
	*,
	fecha: str | date | None = None,
	fecha_desde: str | date | None = None,
	fecha_hasta: str | date | None = None,
	fechas: str | list | None = None,
) -> bytes:
	from frappe.utils.pdf import get_pdf

	html = build_ocupacion_reporte_html(
		fecha=fecha,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		fechas=fechas,
	)
	return get_pdf(html, options=ocupacion_pdf_wkhtml_options())


def reporte_pdf_filename(
	*,
	fecha: str | date | None = None,
	fecha_desde: str | date | None = None,
	fecha_hasta: str | date | None = None,
	fechas: str | list | None = None,
) -> str:
	dias = normalize_fechas_reporte(
		fecha=fecha,
		fecha_desde=fecha_desde,
		fecha_hasta=fecha_hasta,
		fechas=fechas,
	)
	if len(dias) == 1:
		return f"ocupacion_espacios_{dias[0]}"
	return f"ocupacion_espacios_{dias[0]}_{dias[-1]}"
