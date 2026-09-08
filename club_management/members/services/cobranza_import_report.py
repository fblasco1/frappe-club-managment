"""Informe HTML de cobranza socio a socio (import Excel y seguimiento post-roster)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import escape_html, flt, getdate, now_datetime, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	format_periodo_cobro,
)
from club_management.members.services.informe_html_common import (
	badge,
	desk_form_link,
	desk_socio_link,
	render_collapsible_section,
	render_nav_bar,
	render_table,
	report_page_shell,
)

COBRANZA_HTML_FILENAME = "INFORME COBRANZA IMPORT.html"
LATEST_COBRANZA_HTML_SITE_PATH = "private/files/cobranza_import_latest.html"
INFORME_COBRANZA_URL = "/informe-import-cobranza-basquet"
INFORME_ROSTER_URL = "/informe-import-roster-basquet"

MOTIVO_YA_COBRADA = "Factura ya cobrada"
MOTIVO_SIN_FACTURA = "Sin factura pendiente coincidente"


def find_latest_cobranza_import_log() -> str | None:
	"""Devuelve la ruta del último log apply de import_cobranza_excel."""
	log_dir = Path(frappe.get_site_path("private", "logs", "cobranza"))
	if not log_dir.is_dir():
		return None
	candidates = sorted(log_dir.glob("import-cobranza-apply-*.json"), reverse=True)
	return str(candidates[0]) if candidates else None


def load_cobranza_import_log(log_path: str | None = None) -> dict[str, Any] | None:
	path = Path(log_path) if log_path else None
	if path is None or not path.is_file():
		path_str = find_latest_cobranza_import_log()
		if not path_str:
			return None
		path = Path(path_str)
	if not path.is_file():
		return None
	return json.loads(path.read_text(encoding="utf-8"))


def index_cobranza_log_by_socio(log: dict[str, Any]) -> dict[str, dict[str, list[dict[str, Any]]]]:
	"""Agrupa filas del log de cobranza por socio."""
	indexed: dict[str, dict[str, list[dict[str, Any]]]] = {}
	for bucket, key in (("ok", "ok"), ("omitidos", "omitidos_detalle"), ("errores", "errores_detalle")):
		for row in log.get(key) or []:
			socio = str(row.get("socio") or "").strip()
			if not socio:
				continue
			indexed.setdefault(socio, {"ok": [], "omitidos": [], "errores": []})
			indexed[socio][bucket].append(row)
	return indexed


def _invoice_kind(remarks: str | None) -> str:
	text = (remarks or "").lower()
	if "aranceles" in text:
		return "aranceles"
	if "cuota mensual" in text:
		return "cuota"
	return "otro"


def get_socio_facturas_periodo(socio_name: str, periodo_cobro: str) -> list[dict[str, Any]]:
	"""Facturas submitted del período para un socio."""
	campo_socio = _campo_socio_en(SALES_INVOICE_DOCTYPE)
	if not campo_socio:
		return []
	filters: dict[str, Any] = {campo_socio: socio_name, "docstatus": 1}
	campo_periodo = _campo_periodo_cobro()
	if campo_periodo:
		filters[campo_periodo] = periodo_cobro
	rows = frappe.get_all(
		SALES_INVOICE_DOCTYPE,
		filters=filters,
		fields=["name", "remarks", "outstanding_amount", "grand_total", "posting_date"],
		order_by="posting_date asc, name asc",
	)
	result: list[dict[str, Any]] = []
	for row in rows:
		result.append(
			{
				"name": row.name,
				"tipo": _invoice_kind(row.remarks),
				"remarks": row.remarks or "",
				"outstanding": flt(row.outstanding_amount),
				"total": flt(row.grand_total),
				"posting_date": str(row.posting_date or ""),
			}
		)
	return result


def classify_omitido_row(row: dict[str, Any]) -> dict[str, str]:
	"""Distingue ya cobrada vs sin factura vs sin coincidencia (no son lo mismo)."""
	motivo = str(row.get("motivo") or "").strip()
	socio = str(row.get("socio") or "").strip()
	periodo = str(row.get("periodo") or "").strip()

	if motivo == MOTIVO_YA_COBRADA:
		return {
			"estado": "cobrada",
			"estado_label": "Ya cobrada",
			"estado_detalle": "El Excel tenía un cobro pero la factura ya estaba saldada.",
		}

	if not socio or not frappe.db.exists("Socio", socio):
		return {
			"estado": "sin_factura",
			"estado_label": "Sin factura",
			"estado_detalle": motivo or "Socio no encontrado; no se puede verificar facturación.",
		}

	facturas = get_socio_facturas_periodo(socio, periodo) if periodo else []
	if not facturas:
		return {
			"estado": "sin_factura",
			"estado_label": "Sin factura",
			"estado_detalle": f"No tiene facturas emitidas para el período {periodo or '—'}.",
		}

	pending = [f for f in facturas if f["outstanding"] > 0]
	if not pending:
		return {
			"estado": "cobrada",
			"estado_label": "Ya cobrada",
			"estado_detalle": "Tiene facturas del período pero todas están saldadas.",
		}

	return {
		"estado": "sin_coincidencia",
		"estado_label": "Sin coincidencia",
		"estado_detalle": (
			f"Tiene {len(pending)} factura(s) pendiente(s) que no coinciden con importe/concepto del Excel."
		),
	}


def enrich_omitidos_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	enriched: list[dict[str, Any]] = []
	for row in rows:
		cls = classify_omitido_row(row)
		enriched.append({**row, **cls})
	return enriched


def split_omitidos_by_estado(
	rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
	"""Separa omitidos en ya cobrada, sin factura y sin coincidencia."""
	enriched = enrich_omitidos_rows(rows)
	ya_cobrada = [r for r in enriched if r["estado"] == "cobrada"]
	sin_factura = [r for r in enriched if r["estado"] == "sin_factura"]
	sin_coincidencia = [r for r in enriched if r["estado"] == "sin_coincidencia"]
	return ya_cobrada, sin_factura, sin_coincidencia


def _estado_factura_cell(factura: dict[str, Any] | None) -> str:
	if not factura:
		return badge("sin_factura", "Sin factura")
	if factura["outstanding"] <= 0:
		link = desk_form_link("sales-invoice", factura["name"])
		return f"{badge('cobrada', 'Cobrada')} {link}"
	link = desk_form_link("sales-invoice", factura["name"])
	return f"{badge('pendiente', f'Pendiente ${factura['outstanding']}')} {link}"


def _summarize_cobranza_log_rows(rows: dict[str, list[dict[str, Any]]]) -> str:
	parts: list[str] = []
	if rows.get("ok"):
		last = rows["ok"][-1]
		parts.append(
			f"Cobro registrado: {last.get('payment_entry') or '—'} "
			f"(${last.get('importe')}) → {last.get('sales_invoice') or '—'}"
		)
	for row in rows.get("omitidos") or []:
		cls = classify_omitido_row(row)
		parts.append(f"Omitido Excel ({cls['estado_label']}): {row.get('concepto') or '—'}")
	for row in rows.get("errores") or []:
		parts.append(f"Error Excel: {row.get('error') or '—'}")
	return " · ".join(parts) if parts else "Sin movimientos en import Excel"


def _suggest_cobranza_action(
	*,
	facturas: list[dict[str, Any]],
	cobranza_rows: dict[str, list[dict[str, Any]]],
	tiene_inscripcion_nueva: bool,
) -> str:
	arancel = next((f for f in facturas if f["tipo"] == "aranceles"), None)
	cuota = next((f for f in facturas if f["tipo"] == "cuota"), None)
	if cobranza_rows.get("errores"):
		return "Revisar error del import Excel y corregir socio/factura en Desk"
	if tiene_inscripcion_nueva and not arancel:
		return "Emitir aranceles del período (emitir_aranceles_periodo) y luego registrar cobro"
	if arancel and arancel["outstanding"] > 0:
		if cobranza_rows.get("omitidos"):
			return "Registrar cobro manual: factura pendiente y fila omitida en Excel"
		return "Registrar cobro manual en ficha Socio (factura aranceles pendiente)"
	if cuota and cuota["outstanding"] > 0:
		return "Registrar cobro de cuota social pendiente"
	if cobranza_rows.get("ok"):
		return "OK — cobro importado; verificar saldo en Socio"
	if tiene_inscripcion_nueva:
		return "Verificar facturación julio tras inscripción nueva"
	return "Sin acción pendiente detectada"


def build_cobranza_followup_rows(
	inscripciones_nuevas: list[dict[str, str]],
	*,
	periodo_cobro: str,
	cobranza_log: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
	"""Filas socio a socio para Secretaría (inscripción + facturas + import Excel)."""
	by_socio = index_cobranza_log_by_socio(cobranza_log) if cobranza_log else {}
	rows: list[dict[str, Any]] = []
	for entry in inscripciones_nuevas:
		socio_name = entry.get("socio") or ""
		if not socio_name:
			continue
		socio_row = frappe.db.get_value(
			"Socio",
			socio_name,
			["nombre_completo", "dni", "saldo_deuda"],
			as_dict=True,
		) or {}
		facturas = get_socio_facturas_periodo(socio_name, periodo_cobro)
		arancel = next((f for f in facturas if f["tipo"] == "aranceles"), None)
		cuota = next((f for f in facturas if f["tipo"] == "cuota"), None)
		cobranza = by_socio.get(socio_name, {})
		rows.append(
			{
				"socio": socio_name,
				"dni": entry.get("dni") or socio_row.get("dni") or "",
				"nombre": entry.get("nombre") or socio_row.get("nombre_completo") or "",
				"destino": entry.get("destino") or "",
				"_arancel": arancel,
				"_cuota": cuota,
				"saldo_deuda_socio": str(flt(socio_row.get("saldo_deuda"))),
				"import_excel": _summarize_cobranza_log_rows(cobranza),
				"accion": _suggest_cobranza_action(
					facturas=facturas,
					cobranza_rows=cobranza,
					tiene_inscripcion_nueva=True,
				),
			}
		)
	return rows


def _socio_renderer(row: dict[str, Any]) -> str:
	return desk_socio_link(row.get("socio"), row.get("nombre") or row.get("socio"))


def _estado_renderer(row: dict[str, Any]) -> str:
	detalle = row.get("estado_detalle") or ""
	return f"{badge(row.get('estado', ''), row.get('estado_label', ''))}<br><small>{escape_html(detalle)}</small>"


def _invoice_link_renderer(key: str) -> Any:
	def _render(row: dict[str, Any]) -> str:
		return desk_form_link("sales-invoice", row.get(key))

	return _render


def _payment_link_renderer(row: dict[str, Any]) -> str:
	return desk_form_link("payment-entry", row.get("payment_entry"))


def _aranceles_estado_renderer(row: dict[str, Any]) -> str:
	return _estado_factura_cell(row.get("_arancel"))


def _cuota_estado_renderer(row: dict[str, Any]) -> str:
	return _estado_factura_cell(row.get("_cuota"))


def render_cobranza_import_report_html(
	log: dict[str, Any] | None,
	*,
	periodo_cobro: str,
	followup_rows: list[dict[str, Any]] | None = None,
) -> str:
	"""Página HTML completa e independiente del informe de cobranza."""
	followup_rows = followup_rows or []
	if not log and not followup_rows:
		return report_page_shell(
			title="Informe cobranza",
			header_html="<header><h1>Informe cobranza</h1><p>Sin datos disponibles.</p></header>",
			body_html="<p class='empty'>Ejecutá el import de cobranza o el import roster para generar este informe.</p>",
			nav_html=render_nav_bar(
				sibling_href=INFORME_ROSTER_URL,
				sibling_label="Informe import roster básquet",
				toc=[],
			),
		)

	resumen = (log or {}).get("resumen") or {}
	omitidos_raw = (log or {}).get("omitidos_detalle") or []
	ya_cobrada, sin_factura, sin_coincidencia = split_omitidos_by_estado(omitidos_raw)

	action_items: list[str] = []
	if sin_factura:
		action_items.append(
			f"<li><strong>{len(sin_factura)}</strong> filas sin factura emitida: "
			"emitir aranceles/cuota del período antes de registrar cobro.</li>"
		)
	if sin_coincidencia:
		action_items.append(
			f"<li><strong>{len(sin_coincidencia)}</strong> filas sin coincidencia: "
			"revisar importe/concepto en Excel vs factura pendiente en Desk.</li>"
		)
	if ya_cobrada:
		action_items.append(
			f"<li><strong>{len(ya_cobrada)}</strong> filas ya cobradas: "
			"no requieren acción (el Excel repite un cobro existente).</li>"
		)
	if resumen.get("errores"):
		action_items.append(
			f"<li><strong>{resumen['errores']}</strong> errores del Excel: "
			"socio inexistente o datos inconsistentes; corregir padrón o Excel.</li>"
		)
	if followup_rows:
		pendientes = sum(1 for r in followup_rows if "OK" not in (r.get("accion") or ""))
		if pendientes:
			action_items.append(
				f"<li><strong>{pendientes}</strong> inscripciones nuevas con seguimiento de cobranza pendiente.</li>"
			)

	if action_items:
		action_block = (
			'<div class="action-pending"><h2>Qué corregir a mano</h2><ol>'
			+ "".join(action_items)
			+ "</ol></div>"
		)
	else:
		action_block = (
			'<div class="action-ok"><p>Cobranza del período sin pendientes detectados en este informe.</p></div>'
		)

	kpis: list[tuple[str, int]] = []
	if log:
		kpis = [
			("Cobros registrados", int(resumen.get("procesados") or 0)),
			("Omitidos — ya cobrada", len(ya_cobrada)),
			("Omitidos — sin factura", len(sin_factura)),
			("Omitidos — sin coincidencia", len(sin_coincidencia)),
			("Errores Excel", int(resumen.get("errores") or 0)),
		]
	if followup_rows:
		kpis.append(("Inscrip. nuevas a revisar", len(followup_rows)))

	kpi_html = '<div class="kpis">' + "".join(
		f'<div class="kpi"><span class="kpi-label">{escape_html(label)}</span>'
		f'<span class="kpi-value">{value}</span></div>'
		for label, value in kpis
	) + "</div>"

	toc: list[tuple[str, str]] = []
	sections: list[str] = []

	if followup_rows:
		toc.append(("seguimiento-inscripciones", "Inscripciones nuevas"))
		sections.append(
			render_collapsible_section(
				"seguimiento-inscripciones",
				f"Seguimiento — inscripciones nuevas ({len(followup_rows)})",
				f"Estado facturas {periodo_cobro} y resultado del import Excel, socio a socio.",
				render_table(
					followup_rows,
					[
						("socio", "Socio"),
						("dni", "DNI"),
						("destino", "Inscripción"),
						("_arancel", "Aranceles"),
						("_cuota", "Cuota social"),
						("saldo_deuda_socio", "Saldo deuda"),
						("import_excel", "Import Excel"),
						("accion", "Acción sugerida"),
					],
					renderers={
						"socio": _socio_renderer,
						"_arancel": _aranceles_estado_renderer,
						"_cuota": _cuota_estado_renderer,
					},
				),
				open_default=True,
			)
		)

	if log:
		toc.append(("excel-registrados", "Excel registrados"))
		sections.append(
			render_collapsible_section(
				"excel-registrados",
				f"Excel — registrados ({resumen.get('procesados', 0)})",
				"Payment Entry creados desde el Excel.",
				render_table(
					log.get("ok") or [],
					[
						("fecha", "Fecha"),
						("socio", "Socio"),
						("concepto", "Concepto"),
						("importe", "Importe"),
						("sales_invoice", "Factura"),
						("payment_entry", "Payment Entry"),
						("mode_of_payment", "Medio"),
					],
					renderers={
						"socio": _socio_renderer,
						"sales_invoice": _invoice_link_renderer("sales_invoice"),
						"payment_entry": _payment_link_renderer,
					},
				),
			)
		)

		omit_cols = [
			("fecha", "Fecha"),
			("socio", "Socio"),
			("concepto", "Concepto"),
			("importe", "Importe"),
			("periodo", "Período"),
			("estado", "Estado"),
			("motivo", "Motivo Excel"),
		]
		omit_renderers = {"socio": _socio_renderer, "estado": _estado_renderer}

		if ya_cobrada:
			toc.append(("excel-ya-cobrada", "Ya cobrada"))
			sections.append(
				render_collapsible_section(
					"excel-ya-cobrada",
					f"Excel omitidos — ya cobrada ({len(ya_cobrada)})",
					"El Excel repite un cobro que ya estaba registrado; no requiere acción.",
					render_table(ya_cobrada, omit_cols, renderers=omit_renderers),
				)
			)
		if sin_factura:
			toc.append(("excel-sin-factura", "Sin factura"))
			sections.append(
				render_collapsible_section(
					"excel-sin-factura",
					f"Excel omitidos — sin factura ({len(sin_factura)})",
					"No hay factura emitida para el período; emitir deuda antes de cobrar.",
					render_table(sin_factura, omit_cols, renderers=omit_renderers),
					open_default=True,
				)
			)
		if sin_coincidencia:
			toc.append(("excel-sin-coincidencia", "Sin coincidencia"))
			sections.append(
				render_collapsible_section(
					"excel-sin-coincidencia",
					f"Excel omitidos — sin coincidencia ({len(sin_coincidencia)})",
					"Hay factura pendiente pero importe/concepto no coincide con el Excel.",
					render_table(sin_coincidencia, omit_cols, renderers=omit_renderers),
					open_default=True,
				)
			)

		toc.append(("excel-errores", "Errores"))
		sections.append(
			render_collapsible_section(
				"excel-errores",
				f"Excel — errores ({resumen.get('errores', 0)})",
				"Socios o datos que fallaron al importar.",
				render_table(
					log.get("errores_detalle") or [],
					[
						("fecha", "Fecha"),
						("socio", "Socio"),
						("concepto", "Concepto"),
						("importe", "Importe"),
						("error", "Error"),
					],
					renderers={"socio": _socio_renderer},
				),
				open_default=bool(resumen.get("errores")),
			)
		)

	generated_at = now_datetime()
	timestamp = generated_at.strftime("%d/%m/%Y %H:%M") if hasattr(generated_at, "strftime") else str(generated_at)

	meta = ""
	if log:
		meta = (
			f"<p>Período: {escape_html(periodo_cobro)} · "
			f"Excel: {escape_html(str(log.get('file_path') or '—'))} · "
			f"Rango: {escape_html(str(log.get('fecha_desde') or '—'))} → "
			f"{escape_html(str(log.get('fecha_hasta') or '—'))}</p>"
		)

	header = f"""
<header>
  <h1>Informe cobranza — detalle socio a socio</h1>
  {meta}
  <p>Generado: {escape_html(timestamp)}</p>
</header>"""

	nav = render_nav_bar(
		sibling_href=INFORME_ROSTER_URL,
		sibling_label="Informe import roster básquet",
		toc=toc,
	)

	body = action_block + kpi_html + "".join(sections)

	return report_page_shell(
		title="Informe cobranza",
		header_html=header,
		body_html=body,
		nav_html=nav,
	)


def write_cobranza_import_report_html(
	log: dict[str, Any] | None,
	*,
	output_dir: str | Path | None = None,
	publish_latest: bool = True,
	followup_rows: list[dict[str, Any]] | None = None,
	periodo_cobro: str | None = None,
) -> str:
	periodo = periodo_cobro or (log or {}).get("fecha_desde") or format_periodo_cobro(today())
	if isinstance(periodo, str) and len(periodo) == 10:
		periodo = format_periodo_cobro(getdate(periodo))
	html = render_cobranza_import_report_html(
		log,
		periodo_cobro=str(periodo),
		followup_rows=followup_rows,
	)
	written_path = ""
	if output_dir:
		out = Path(output_dir)
		out.mkdir(parents=True, exist_ok=True)
		path = out / COBRANZA_HTML_FILENAME
		path.write_text(html, encoding="utf-8")
		written_path = str(path)
	if publish_latest:
		latest = Path(frappe.get_site_path(LATEST_COBRANZA_HTML_SITE_PATH))
		latest.parent.mkdir(parents=True, exist_ok=True)
		latest.write_text(html, encoding="utf-8")
		if not written_path:
			written_path = str(latest)
	return written_path
