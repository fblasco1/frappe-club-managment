"""Informe HTML del import roster básquet Jugadorxs (spec vinculacion_basquet_roster.md)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import escape_html, now_datetime, today

from club_management.members.services.cobranza_manual import format_periodo_cobro
from club_management.members.services.informe_html_common import (
	desk_socio_link,
	render_collapsible_section,
	render_nav_bar,
	render_table,
	report_page_shell,
)

REPORT_FILENAME = "INFORME IMPORT ROSTER BASQUET.html"
LATEST_REPORT_SITE_PATH = "private/files/roster_import_basquet_latest.html"
INFORME_ROSTER_URL = "/informe-import-roster-basquet"
INFORME_COBRANZA_URL = "/informe-import-cobranza-basquet"


def _pending_count(stats: dict[str, Any]) -> int:
	return (
		int(stats.get("no_padron_sin_dni") or 0)
		+ int(stats.get("no_padron_con_dni") or 0)
		+ len(stats.get("errores") or [])
	)


def _completion_pct(stats: dict[str, Any]) -> float:
	total = int(stats.get("total_filas") or 0) - int(stats.get("omitidos_duplicado_csv") or 0)
	if total <= 0:
		return 100.0
	done = int(stats.get("inscripciones_nuevas") or 0) + int(stats.get("ya_inscriptos") or 0)
	return round(min(100.0, (done / total) * 100), 1)


def _render_errors(errors: list[str]) -> str:
	if not errors:
		return '<p class="empty">Sin errores.</p>'
	items = "".join(f"<li>{escape_html(err)}</li>" for err in errors)
	return f"<ul class='error-list'>{items}</ul>"


def _socio_renderer(row: dict[str, Any]) -> str:
	return desk_socio_link(row.get("socio"), row.get("nombre") or row.get("socio"))


def render_roster_import_report_html(
	stats: dict[str, Any],
	*,
	source_path: str,
	dry_run: bool,
	log_rows: dict[str, list[dict[str, str]]] | None = None,
) -> str:
	"""Genera HTML autocontenido con resumen y guía de ajustes (solo inscripciones)."""
	log_rows = log_rows or {}
	pending = _pending_count(stats)
	completion = _completion_pct(stats)
	mode = "Simulación (dry_run)" if dry_run else "Import ejecutado"
	generated_at = now_datetime()
	if isinstance(generated_at, datetime):
		timestamp = generated_at.strftime("%d/%m/%Y %H:%M")
	else:
		timestamp = str(generated_at)

	action_items: list[str] = []
	if stats.get("no_padron_sin_dni"):
		action_items.append(
			f"<li><strong>{stats['no_padron_sin_dni']}</strong> jugadores sin DNI en el CSV: "
			"verificar que el nombre coincida exactamente con el padrón "
			"(apellido, nombre), agregar DNI al CSV o dar de alta el socio en el padrón.</li>"
		)
	if stats.get("no_padron_con_dni"):
		action_items.append(
			f"<li><strong>{stats['no_padron_con_dni']}</strong> jugadores con DNI que no están en el padrón: "
			"crear el socio con ese DNI o corregir el DNI en el CSV si está mal cargado.</li>"
		)
	if stats.get("errores"):
		action_items.append(
			f"<li><strong>{len(stats['errores'])}</strong> errores de mapeo o estructura: "
			"revisar categoría/equipo del CSV frente a la estructura unificada de Básquet "
			"(grupos y equipos en Gestión de Actividades).</li>"
		)
	if not action_items:
		action_block = (
			'<div class="action-ok">'
			"<p>El import está completo para todas las filas procesables. "
			"No quedan pendientes de ajuste en padrón ni errores de mapeo.</p></div>"
		)
	else:
		action_block = (
			'<div class="action-pending"><h2>Qué ajustar para completar el import</h2><ol>'
			+ "".join(action_items)
			+ "</ol></div>"
		)

	kpis = [
		("Filas válidas", stats.get("total_filas", 0)),
		("Inscripciones nuevas", stats.get("inscripciones_nuevas", 0)),
		("Ya inscriptos", stats.get("ya_inscriptos", 0)),
		("No padrón sin DNI", stats.get("no_padron_sin_dni", 0)),
		("No padrón con DNI", stats.get("no_padron_con_dni", 0)),
		("Duplicados CSV", stats.get("omitidos_duplicado_csv", 0)),
		("Errores", len(stats.get("errores") or [])),
		("Pendientes", pending),
	]
	kpi_html = '<div class="kpis">' + "".join(
		f'<div class="kpi"><span class="kpi-label">{escape_html(label)}</span>'
		f'<span class="kpi-value">{value}</span></div>'
		for label, value in kpis
	) + "</div>"

	base_columns = [
		("numero", "Nº"),
		("dni", "DNI"),
		("nombre", "Nombre"),
		("categoria", "Categoría"),
		("equipo", "Equipo"),
	]
	ya_columns = base_columns + [
		("socio", "Socio"),
		("inscripcion_existente", "Inscripción existente"),
	]
	nuevas_columns = base_columns + [
		("socio", "Socio"),
		("destino", "Destino"),
	]
	socio_renderer = {"socio": _socio_renderer}

	toc: list[tuple[str, str]] = [
		("inscripciones-nuevas", "Inscripciones nuevas"),
		("ya-inscriptos", "Ya inscriptos"),
		("no-padron-sin-dni", "Sin DNI"),
		("no-padron-con-dni", "DNI sin padrón"),
		("errores", "Errores"),
	]

	sections = [
		render_collapsible_section(
			"inscripciones-nuevas",
			f"Inscripciones nuevas ({stats.get('inscripciones_nuevas', 0)})",
			"Filas que se inscribieron correctamente en esta ejecución. Clic en socio abre la ficha en Desk.",
			render_table(
				log_rows.get("inscripciones_nuevas") or [],
				nuevas_columns,
				renderers=socio_renderer,
			),
			open_default=stats.get("inscripciones_nuevas", 0) > 0,
		),
		render_collapsible_section(
			"ya-inscriptos",
			f"Ya tenían inscripción ({stats.get('ya_inscriptos', 0)})",
			"No requieren acción: ya tenían básquet activo.",
			render_table(
				log_rows.get("ya_inscriptos") or [],
				ya_columns,
				renderers=socio_renderer,
			),
		),
		render_collapsible_section(
			"no-padron-sin-dni",
			f"No están en el padrón y sin DNI ({stats.get('no_padron_sin_dni', 0)})",
			"Prioridad: corregir nombre o agregar DNI para vincular con un socio existente.",
			render_table(log_rows.get("no_padron_sin_dni") or [], base_columns),
			open_default=stats.get("no_padron_sin_dni", 0) > 0,
		),
		render_collapsible_section(
			"no-padron-con-dni",
			f"No están en el padrón pero tienen DNI ({stats.get('no_padron_con_dni', 0)})",
			"Prioridad: alta de socio en padrón o corrección del DNI en el CSV.",
			render_table(log_rows.get("no_padron_con_dni") or [], base_columns),
			open_default=stats.get("no_padron_con_dni", 0) > 0,
		),
		render_collapsible_section(
			"errores",
			f"Errores ({len(stats.get('errores') or [])})",
			"Fallos de mapeo o estructura; revisar categoría/equipo y seed de actividades.",
			_render_errors(stats.get("errores") or []),
			open_default=len(stats.get("errores") or []) > 0,
		),
	]

	csv_links = stats.get("log_paths") or {}
	csv_list = "".join(
		f"<li><code>{escape_html(key)}</code>: {escape_html(path)}</li>"
		for key, path in csv_links.items()
		if key != "reporte_html"
	)
	files_block = f"""
<div class="files">
  <strong>Archivos CSV de log</strong>
  <ul>{csv_list or "<li>Sin CSV generados.</li>"}</ul>
</div>"""

	header = f"""
<header>
  <h1>Informe import roster básquet</h1>
  <p>Modo: {escape_html(mode)}</p>
  <p>Archivo: {escape_html(source_path)}</p>
  <p>Generado: {escape_html(timestamp)}</p>
  <div class="progress"><div class="progress-bar" style="width:{completion}%"></div></div>
  <p class="progress-label">Completitud: {completion}% — pendientes: {pending}</p>
</header>"""

	nav = render_nav_bar(
		sibling_href=INFORME_COBRANZA_URL,
		sibling_label="Informe cobranza (facturas y Excel)",
		toc=toc,
	)

	body = action_block + kpi_html + "".join(sections) + files_block

	return report_page_shell(
		title="Informe import roster básquet",
		header_html=header,
		body_html=body,
		nav_html=nav,
	)


def write_roster_import_report(
	stats: dict[str, Any],
	*,
	source_path: str,
	dry_run: bool,
	output_dir: str | Path,
	log_rows: dict[str, list[dict[str, str]]] | None = None,
	publish_latest: bool = True,
	cobranza_periodo: str | None = None,
	cobranza_log_path: str | None = None,
	write_cobranza_page: bool = True,
) -> str:
	"""Escribe informe HTML de roster y, por separado, el de cobranza."""
	out_dir = Path(output_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	html = render_roster_import_report_html(
		stats,
		source_path=source_path,
		dry_run=dry_run,
		log_rows=log_rows,
	)
	path = out_dir / REPORT_FILENAME
	path.write_text(html, encoding="utf-8")
	if publish_latest:
		latest = Path(frappe.get_site_path(LATEST_REPORT_SITE_PATH))
		latest.parent.mkdir(parents=True, exist_ok=True)
		latest.write_text(html, encoding="utf-8")

	if write_cobranza_page and not dry_run:
		from club_management.members.services.cobranza_import_report import (
			build_cobranza_followup_rows,
			load_cobranza_import_log,
			write_cobranza_import_report_html,
		)

		periodo = cobranza_periodo or format_periodo_cobro(today())
		cobranza_log = load_cobranza_import_log(cobranza_log_path)
		followup_rows = build_cobranza_followup_rows(
			(log_rows or {}).get("inscripciones_nuevas") or [],
			periodo_cobro=periodo,
			cobranza_log=cobranza_log,
		)
		cobranza_path = write_cobranza_import_report_html(
			cobranza_log,
			output_dir=out_dir,
			followup_rows=followup_rows,
			periodo_cobro=periodo,
		)
		stats.setdefault("log_paths", {})["reporte_cobranza_html"] = cobranza_path

	return str(path)
