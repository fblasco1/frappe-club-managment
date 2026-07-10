"""Informe HTML de cobranza socio a socio (import Excel y seguimiento post-roster)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import escape_html, flt, getdate, today

from club_management.members.services.cobranza_manual import (
	SALES_INVOICE_DOCTYPE,
	_campo_periodo_cobro,
	_campo_socio_en,
	format_periodo_cobro,
)

COBRANZA_HTML_FILENAME = "INFORME COBRANZA IMPORT.html"
LATEST_COBRANZA_HTML_SITE_PATH = "private/files/cobranza_import_latest.html"


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


def _summarize_cobranza_log_rows(rows: dict[str, list[dict[str, Any]]]) -> str:
	parts: list[str] = []
	if rows.get("ok"):
		last = rows["ok"][-1]
		parts.append(
			f"Cobro registrado: {last.get('payment_entry') or '—'} "
			f"(${last.get('importe')}) → {last.get('sales_invoice') or '—'}"
		)
	for row in rows.get("omitidos") or []:
		parts.append(f"Omitido Excel: {row.get('motivo') or '—'} ({row.get('concepto') or '—'})")
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
) -> list[dict[str, str]]:
	"""Filas socio a socio para Secretaría (inscripción + facturas + import Excel)."""
	by_socio = index_cobranza_log_by_socio(cobranza_log) if cobranza_log else {}
	rows: list[dict[str, str]] = []
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
				"factura_aranceles": arancel["name"] if arancel else "",
				"saldo_aranceles": str(arancel["outstanding"]) if arancel else "",
				"factura_cuota": cuota["name"] if cuota else "",
				"saldo_cuota": str(cuota["outstanding"]) if cuota else "",
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


def _render_cobranza_log_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
	if not rows:
		return '<p class="empty">Sin registros.</p>'
	head = "".join(f"<th>{escape_html(label)}</th>" for _, label in columns)
	body: list[str] = []
	for row in rows:
		cells = "".join(
			f"<td>{escape_html(str(row.get(key) or ''))}</td>" for key, _ in columns
		)
		body.append(f"<tr>{cells}</tr>")
	return (
		'<div class="table-wrap"><table><thead><tr>'
		+ head
		+ "</tr></thead><tbody>"
		+ "".join(body)
		+ "</tbody></table></div>"
	)


def render_cobranza_import_sections_html(
	log: dict[str, Any] | None,
	*,
	periodo_cobro: str,
	followup_rows: list[dict[str, str]] | None = None,
) -> str:
	"""HTML de secciones de cobranza para incrustar en informes."""
	followup_rows = followup_rows or []
	if not log and not followup_rows:
		return ""

	resumen = (log or {}).get("resumen") or {}
	action_items: list[str] = []
	if resumen.get("omitidos"):
		action_items.append(
			f"<li><strong>{resumen['omitidos']}</strong> filas del Excel omitidas: "
			"revisar factura pendiente, importe o concepto; registrar cobro manual en Socio.</li>"
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
			'<div class="action-pending cobranza-block"><h2>Cobranza — qué corregir a mano</h2><ol>'
			+ "".join(action_items)
			+ "</ol></div>"
		)
	else:
		action_block = (
			'<div class="action-ok cobranza-block"><p>Cobranza julio sin pendientes detectados en este informe.</p></div>'
		)

	kpis = []
	if log:
		kpis = [
			("Cobros registrados", resumen.get("procesados", 0)),
			("Omitidos Excel", resumen.get("omitidos", 0)),
			("Errores Excel", resumen.get("errores", 0)),
		]
	if followup_rows:
		kpis.append(("Inscrip. nuevas a revisar", len(followup_rows)))

	kpi_html = ""
	if kpis:
		kpi_html = '<div class="kpis cobranza-kpis">' + "".join(
			f'<div class="kpi"><span class="kpi-label">{escape_html(l)}</span>'
			f'<span class="kpi-value">{v}</span></div>'
			for l, v in kpis
		) + "</div>"

	followup_cols = [
		("socio", "Socio"),
		("dni", "DNI"),
		("nombre", "Nombre"),
		("destino", "Inscripción"),
		("factura_aranceles", "Factura aranceles"),
		("saldo_aranceles", "Saldo aranceles"),
		("factura_cuota", "Factura cuota"),
		("saldo_cuota", "Saldo cuota"),
		("saldo_deuda_socio", "Saldo deuda socio"),
		("import_excel", "Import Excel"),
		("accion", "Acción sugerida"),
	]

	excel_ok_cols = [
		("fecha", "Fecha"),
		("socio", "Socio"),
		("nombre", "Nombre"),
		("concepto", "Concepto"),
		("importe", "Importe"),
		("sales_invoice", "Factura"),
		("payment_entry", "Payment Entry"),
		("mode_of_payment", "Medio"),
	]
	excel_omit_cols = [
		("fecha", "Fecha"),
		("socio", "Socio"),
		("nombre", "Nombre"),
		("concepto", "Concepto"),
		("importe", "Importe"),
		("periodo", "Período"),
		("motivo", "Motivo"),
	]
	excel_err_cols = [
		("fecha", "Fecha"),
		("socio", "Socio"),
		("nombre", "Nombre"),
		("concepto", "Concepto"),
		("importe", "Importe"),
		("error", "Error"),
	]

	sections: list[tuple[str, str, str, str, bool]] = []
	if followup_rows:
		sections.append(
			(
				"cobranza-inscripciones-nuevas",
				f"Seguimiento cobranza — inscripciones nuevas ({len(followup_rows)})",
				f"Estado facturas {periodo_cobro} y resultado del import Excel, socio a socio.",
				_render_cobranza_log_table(followup_rows, followup_cols),
				True,
			)
		)
	if log:
		sections.append(
			(
				"cobranza-excel-ok",
				f"Excel cobranza — registrados ({resumen.get('procesados', 0)})",
				"Payment Entry creados desde el Excel.",
				_render_cobranza_log_table(log.get("ok") or [], excel_ok_cols),
				False,
			)
		)
		sections.append(
			(
				"cobranza-excel-omitidos",
				f"Excel cobranza — omitidos ({resumen.get('omitidos', 0)})",
				"Filas sin factura coincidente o ya cobradas; Secretaría debe revisar y cargar a mano.",
				_render_cobranza_log_table(log.get("omitidos_detalle") or [], excel_omit_cols),
				bool(resumen.get("omitidos")),
			)
		)
		sections.append(
			(
				"cobranza-excel-errores",
				f"Excel cobranza — errores ({resumen.get('errores', 0)})",
				"Socios o datos que fallaron al importar.",
				_render_cobranza_log_table(log.get("errores_detalle") or [], excel_err_cols),
				bool(resumen.get("errores")),
			)
		)

	meta = ""
	if log:
		meta = (
			f"<p class='cobranza-meta'>Período: {escape_html(periodo_cobro)} · "
			f"Excel: {escape_html(str(log.get('file_path') or '—'))} · "
			f"Rango: {escape_html(str(log.get('fecha_desde') or '—'))} → "
			f"{escape_html(str(log.get('fecha_hasta') or '—'))}</p>"
		)

	section_html = ""
	for section_id, title, hint, content, open_default in sections:
		open_attr = " open" if open_default else ""
		section_html += (
			f'<details class="section cobranza-section" id="{section_id}"{open_attr}>'
			f"<summary><span class='section-title'>{escape_html(title)}</span>"
			f"<span class='section-hint'>{escape_html(hint)}</span></summary>"
			f"<div class='section-body'>{content}</div></details>"
		)

	return f"""
<h2 class="report-part-title">Cobranza y cargos — detalle socio a socio</h2>
{meta}
{action_block}
{kpi_html}
{section_html}
"""


def write_cobranza_import_report_html(
	log: dict[str, Any],
	*,
	output_dir: str | Path | None = None,
	publish_latest: bool = True,
	followup_rows: list[dict[str, str]] | None = None,
	periodo_cobro: str | None = None,
) -> str:
	periodo = periodo_cobro or log.get("fecha_desde") or format_periodo_cobro(today())
	if isinstance(periodo, str) and len(periodo) == 10:
		periodo = format_periodo_cobro(getdate(periodo))
	body = render_cobranza_import_sections_html(
		log,
		periodo_cobro=str(periodo),
		followup_rows=followup_rows,
	)
	html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Informe cobranza</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f4f6f8; }}
.report-part-title {{ margin-top: 32px; }}
.cobranza-meta {{ color: #61727a; }}
.action-pending, .action-ok {{ background: #fff; border-radius: 8px; padding: 16px; margin: 16px 0; }}
.action-pending {{ border-left: 4px solid #b45309; }}
.kpis {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 16px 0; }}
.kpi {{ background: #fff; padding: 12px; border-radius: 8px; min-width: 120px; }}
.section {{ background: #fff; margin-bottom: 12px; border-radius: 8px; }}
.section summary {{ padding: 12px 16px; cursor: pointer; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: .9rem; }}
th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px; text-align: left; }}
</style></head><body>{body}</body></html>"""
	if output_dir:
		out = Path(output_dir)
		out.mkdir(parents=True, exist_ok=True)
		path = out / COBRANZA_HTML_FILENAME
		path.write_text(html, encoding="utf-8")
		written_path = str(path)
	else:
		written_path = ""
	if publish_latest:
		latest = Path(frappe.get_site_path(LATEST_COBRANZA_HTML_SITE_PATH))
		latest.parent.mkdir(parents=True, exist_ok=True)
		latest.write_text(html, encoding="utf-8")
	return written_path or str(latest) if publish_latest else written_path
