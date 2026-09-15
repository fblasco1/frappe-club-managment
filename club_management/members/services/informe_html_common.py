"""Utilidades compartidas para informes HTML de Secretaría (navegación Desk)."""

from __future__ import annotations

from typing import Any, Callable

import frappe
from frappe.utils import escape_html, get_url


def desk_base_url() -> str:
	return get_url().rstrip("/")


def desk_socio_link(socio_name: str | None, label: str | None = None) -> str:
	name = (socio_name or "").strip()
	if not name:
		return ""
	text = escape_html(label or name)
	url = f"{desk_base_url()}/app/socio/{escape_html(name)}"
	return f'<a class="desk-link" href="{url}" target="_blank" rel="noopener">{text}</a>'


def desk_form_link(slug: str, docname: str | None, label: str | None = None) -> str:
	name = (docname or "").strip()
	if not name:
		return ""
	text = escape_html(label or name)
	url = f"{desk_base_url()}/app/{slug}/{escape_html(name)}"
	return f'<a class="desk-link" href="{url}" target="_blank" rel="noopener">{text}</a>'


def badge(estado: str, label: str) -> str:
	css = {
		"cobrada": "badge-ok",
		"sin_factura": "badge-warn",
		"sin_coincidencia": "badge-info",
		"pendiente": "badge-pend",
		"error": "badge-err",
		"ok": "badge-ok",
	}.get(estado, "badge-info")
	return f'<span class="badge {css}">{escape_html(label)}</span>'


REPORT_STYLES = """
:root {
  --bg: #f4f6f8;
  --card: #fff;
  --text: #1f2933;
  --muted: #61727a;
  --ok: #0f7b3c;
  --warn: #b45309;
  --err: #b42318;
  --accent: #1d4ed8;
  --border: #d9e2ec;
  --info: #0369a1;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", system-ui, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.45;
}
.wrap { max-width: 1280px; margin: 0 auto; padding: 24px 16px 48px; }
header {
  background: linear-gradient(135deg, #0f172a, #1e3a8a);
  color: #fff;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 16px;
}
header h1 { margin: 0 0 8px; font-size: 1.6rem; }
header p { margin: 4px 0; color: #dbeafe; }
.nav-bar {
  display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 16px; margin-bottom: 16px;
}
.nav-bar a { color: var(--accent); text-decoration: none; font-weight: 600; }
.nav-bar a:hover { text-decoration: underline; }
.nav-toc { display: flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.nav-toc a {
  font-size: .85rem; padding: 4px 10px; border-radius: 999px;
  background: #eef2ff; color: #1e3a8a; text-decoration: none;
}
.toolbar { margin-left: 8px; }
.toolbar button {
  font-size: .82rem; padding: 4px 10px; border-radius: 6px;
  border: 1px solid var(--border); background: #fff; cursor: pointer;
}
.kpis {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 12px; margin-bottom: 20px;
}
.kpi {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px;
}
.kpi-label { display: block; color: var(--muted); font-size: .82rem; }
.kpi-value { display: block; font-size: 1.5rem; font-weight: 700; margin-top: 4px; }
.action-pending, .action-ok {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 20px; margin-bottom: 20px;
}
.action-pending { border-left: 4px solid var(--warn); }
.action-ok { border-left: 4px solid var(--ok); }
.action-pending h2 { margin-top: 0; font-size: 1.1rem; }
.section {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; margin-bottom: 12px; overflow: hidden;
}
.section summary {
  cursor: pointer; list-style: none; padding: 14px 16px;
  display: flex; flex-direction: column; gap: 4px;
}
.section summary::-webkit-details-marker { display: none; }
.section-title { font-weight: 700; }
.section-hint { color: var(--muted); font-size: .9rem; }
.section-body { padding: 0 16px 16px; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .88rem; }
th, td {
  border-bottom: 1px solid var(--border); padding: 8px 10px;
  text-align: left; vertical-align: top;
}
th { background: #f8fafc; position: sticky; top: 0; }
.empty { color: var(--muted); margin: 0; }
.error-list { margin: 0; padding-left: 20px; color: var(--err); }
.desk-link { color: var(--accent); font-weight: 600; text-decoration: none; }
.desk-link:hover { text-decoration: underline; }
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 999px;
  font-size: .78rem; font-weight: 700; white-space: nowrap;
}
.badge-ok { background: #dcfce7; color: #166534; }
.badge-warn { background: #ffedd5; color: #9a3412; }
.badge-info { background: #e0f2fe; color: #075985; }
.badge-pend { background: #fef9c3; color: #854d0e; }
.badge-err { background: #fee2e2; color: #991b1b; }
.progress {
  margin-top: 16px; background: rgba(255,255,255,.2);
  border-radius: 999px; height: 10px; overflow: hidden;
}
.progress-bar { height: 100%; background: #4ade80; }
.progress-label { margin-top: 8px; font-size: .95rem; }
.files {
  background: var(--card); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 20px; margin-top: 20px; font-size: .9rem;
}
code { background: #eef2ff; padding: 2px 6px; border-radius: 4px; }
"""


REPORT_SCRIPTS = """
<script>
function informeToggleAll(open) {
  document.querySelectorAll('details.section').forEach((el) => { el.open = open; });
}
</script>
"""


def render_nav_bar(*, sibling_href: str, sibling_label: str, toc: list[tuple[str, str]]) -> str:
	toc_html = "".join(
		f'<a href="#{escape_html(anchor)}">{escape_html(label)}</a>' for anchor, label in toc
	)
	return f"""
<nav class="nav-bar">
  <a href="{escape_html(sibling_href)}">↗ {escape_html(sibling_label)}</a>
  <div class="nav-toc">{toc_html}</div>
  <div class="toolbar">
    <button type="button" onclick="informeToggleAll(true)">Expandir todo</button>
    <button type="button" onclick="informeToggleAll(false)">Colapsar todo</button>
  </div>
</nav>"""


def render_collapsible_section(
	section_id: str,
	title: str,
	hint: str,
	content: str,
	*,
	open_default: bool = False,
) -> str:
	open_attr = " open" if open_default else ""
	return (
		f'<details class="section" id="{escape_html(section_id)}"{open_attr}>'
		f"<summary><span class='section-title'>{escape_html(title)}</span>"
		f"<span class='section-hint'>{escape_html(hint)}</span></summary>"
		f"<div class='section-body'>{content}</div></details>"
	)


CellRenderer = Callable[[dict[str, Any]], str]


def render_table(
	rows: list[dict[str, Any]],
	columns: list[tuple[str, str]],
	*,
	renderers: dict[str, CellRenderer] | None = None,
) -> str:
	if not rows:
		return '<p class="empty">Sin registros.</p>'
	renderers = renderers or {}
	head = "".join(f"<th>{escape_html(label)}</th>" for _, label in columns)
	body_rows: list[str] = []
	for row in rows:
		cells: list[str] = []
		for key, _ in columns:
			if key in renderers:
				cells.append(f"<td>{renderers[key](row)}</td>")
			else:
				cells.append(f"<td>{escape_html(str(row.get(key) or ''))}</td>")
		body_rows.append(f"<tr>{''.join(cells)}</tr>")
	return (
		'<div class="table-wrap"><table><thead><tr>'
		+ head
		+ "</tr></thead><tbody>"
		+ "".join(body_rows)
		+ "</tbody></table></div>"
	)


def report_page_shell(*, title: str, header_html: str, body_html: str, nav_html: str = "") -> str:
	return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape_html(title)}</title>
<style>{REPORT_STYLES}</style>
</head>
<body>
<div class="wrap">
{header_html}
{nav_html}
{body_html}
</div>
{REPORT_SCRIPTS}
</body>
</html>"""
