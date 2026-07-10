"""Informe HTML del import roster básquet Jugadorxs (spec vinculacion_basquet_roster.md)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import frappe
from frappe.utils import escape_html, now_datetime

REPORT_FILENAME = "INFORME IMPORT ROSTER BASQUET.html"
LATEST_REPORT_SITE_PATH = "private/files/roster_import_basquet_latest.html"


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


def _render_table(rows: list[dict[str, str]], columns: list[tuple[str, str]]) -> str:
	if not rows:
		return '<p class="empty">Sin registros.</p>'
	head = "".join(f"<th>{escape_html(label)}</th>" for _, label in columns)
	body_rows: list[str] = []
	for row in rows:
		cells = "".join(
			f"<td>{escape_html(str(row.get(key) or ''))}</td>" for key, _ in columns
		)
		body_rows.append(f"<tr>{cells}</tr>")
	return (
		'<div class="table-wrap"><table><thead><tr>'
		+ head
		+ "</tr></thead><tbody>"
		+ "".join(body_rows)
		+ "</tbody></table></div>"
	)


def _render_errors(errors: list[str]) -> str:
	if not errors:
		return '<p class="empty">Sin errores.</p>'
	items = "".join(f"<li>{escape_html(err)}</li>" for err in errors)
	return f"<ul class='error-list'>{items}</ul>"


def render_roster_import_report_html(
	stats: dict[str, Any],
	*,
	source_path: str,
	dry_run: bool,
	log_rows: dict[str, list[dict[str, str]]] | None = None,
) -> str:
	"""Genera HTML autocontenido con resumen y guía de ajustes."""
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
	kpi_html = "".join(
		f'<div class="kpi"><span class="kpi-label">{escape_html(label)}</span>'
		f'<span class="kpi-value">{value}</span></div>'
		for label, value in kpis
	)

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

	sections = [
		(
			"inscripciones-nuevas",
			f"Inscripciones nuevas ({stats.get('inscripciones_nuevas', 0)})",
			"Filas que se inscribieron correctamente en esta ejecución.",
			_render_table(log_rows.get("inscripciones_nuevas") or [], nuevas_columns),
			stats.get("inscripciones_nuevas", 0) > 0,
		),
		(
			"ya-inscriptos",
			f"Ya tenían inscripción ({stats.get('ya_inscriptos', 0)})",
			"No requieren acción: ya tenían básquet activo.",
			_render_table(log_rows.get("ya_inscriptos") or [], ya_columns),
			False,
		),
		(
			"no-padron-sin-dni",
			f"No están en el padrón y sin DNI ({stats.get('no_padron_sin_dni', 0)})",
			"Prioridad: corregir nombre o agregar DNI para vincular con un socio existente.",
			_render_table(log_rows.get("no_padron_sin_dni") or [], base_columns),
			stats.get("no_padron_sin_dni", 0) > 0,
		),
		(
			"no-padron-con-dni",
			f"No están en el padrón pero tienen DNI ({stats.get('no_padron_con_dni', 0)})",
			"Prioridad: alta de socio en padrón o corrección del DNI en el CSV.",
			_render_table(log_rows.get("no_padron_con_dni") or [], base_columns),
			stats.get("no_padron_con_dni", 0) > 0,
		),
		(
			"errores",
			f"Errores ({len(stats.get('errores') or [])})",
			"Fallos de mapeo o estructura; revisar categoría/equipo y seed de actividades.",
			_render_errors(stats.get("errores") or []),
			len(stats.get("errores") or []) > 0,
		),
	]
	section_html = ""
	for section_id, title, hint, content, open_default in sections:
		open_attr = " open" if open_default else ""
		section_html += (
			f'<details class="section" id="{section_id}"{open_attr}>'
			f"<summary><span class='section-title'>{escape_html(title)}</span>"
			f"<span class='section-hint'>{escape_html(hint)}</span></summary>"
			f"<div class='section-body'>{content}</div></details>"
		)

	csv_links = stats.get("log_paths") or {}
	csv_list = "".join(
		f"<li><code>{escape_html(key)}</code>: {escape_html(path)}</li>"
		for key, path in csv_links.items()
		if key != "reporte_html"
	)

	return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe import roster básquet</title>
<style>
:root {{
  --bg: #f4f6f8;
  --card: #fff;
  --text: #1f2933;
  --muted: #61727a;
  --ok: #0f7b3c;
  --warn: #b45309;
  --err: #b42318;
  --accent: #1d4ed8;
  --border: #d9e2ec;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.45;
}}
.wrap {{ max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }}
header {{
  background: linear-gradient(135deg, #0f172a, #1e3a8a);
  color: #fff;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 20px;
}}
header h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
header p {{ margin: 4px 0; color: #dbeafe; }}
.progress {{
  margin-top: 16px;
  background: rgba(255,255,255,.2);
  border-radius: 999px;
  height: 10px;
  overflow: hidden;
}}
.progress-bar {{
  height: 100%;
  background: #4ade80;
  width: {completion}%;
}}
.progress-label {{ margin-top: 8px; font-size: .95rem; }}
.kpis {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}}
.kpi {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
}}
.kpi-label {{ display: block; color: var(--muted); font-size: .82rem; }}
.kpi-value {{ display: block; font-size: 1.5rem; font-weight: 700; margin-top: 4px; }}
.action-pending, .action-ok {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  margin-bottom: 20px;
}}
.action-pending {{ border-left: 4px solid var(--warn); }}
.action-ok {{ border-left: 4px solid var(--ok); }}
.action-pending h2 {{ margin-top: 0; font-size: 1.1rem; }}
.section {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  margin-bottom: 12px;
  overflow: hidden;
}}
.section summary {{
  cursor: pointer;
  list-style: none;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}}
.section summary::-webkit-details-marker {{ display: none; }}
.section-title {{ font-weight: 700; }}
.section-hint {{ color: var(--muted); font-size: .9rem; }}
.section-body {{ padding: 0 16px 16px; }}
.table-wrap {{ overflow-x: auto; }}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: .9rem;
}}
th, td {{
  border-bottom: 1px solid var(--border);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}}
th {{ background: #f8fafc; }}
.empty {{ color: var(--muted); margin: 0; }}
.error-list {{ margin: 0; padding-left: 20px; color: var(--err); }}
.files {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  margin-top: 20px;
  font-size: .9rem;
}}
code {{ background: #eef2ff; padding: 2px 6px; border-radius: 4px; }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>Informe import roster básquet</h1>
  <p>Modo: {escape_html(mode)}</p>
  <p>Archivo: {escape_html(source_path)}</p>
  <p>Generado: {escape_html(timestamp)}</p>
  <div class="progress"><div class="progress-bar"></div></div>
  <p class="progress-label">Completitud: {completion}% — pendientes: {pending}</p>
</header>
<div class="kpis">{kpi_html}</div>
{action_block}
{section_html}
<div class="files">
  <strong>Archivos CSV de log</strong>
  <ul>{csv_list or "<li>Sin CSV generados.</li>"}</ul>
</div>
</div>
</body>
</html>"""


def write_roster_import_report(
	stats: dict[str, Any],
	*,
	source_path: str,
	dry_run: bool,
	output_dir: str | Path,
	log_rows: dict[str, list[dict[str, str]]] | None = None,
	publish_latest: bool = True,
) -> str:
	"""Escribe informe HTML en output_dir y opcionalmente publica copia en el sitio."""
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
	return str(path)
