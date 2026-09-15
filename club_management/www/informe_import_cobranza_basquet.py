"""Página autenticada para visualizar el último informe HTML de cobranza."""

from __future__ import annotations

from pathlib import Path

import frappe

from club_management.members.services.cobranza_import_report import (
	LATEST_COBRANZA_HTML_SITE_PATH,
)

_PANEL_ROLES = {"Secretaria", "System Manager"}


def _ensure_access() -> None:
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/informe-import-cobranza-basquet"
		raise frappe.Redirect
	roles = set(frappe.get_roles())
	if not roles.intersection(_PANEL_ROLES):
		frappe.throw(frappe._("No autorizado"), frappe.PermissionError)


def get_context(context):
	_ensure_access()
	context.no_cache = 1
	context.title = "Informe cobranza"
	path = Path(frappe.get_site_path(LATEST_COBRANZA_HTML_SITE_PATH))
	if path.is_file():
		context.report_html = path.read_text(encoding="utf-8")
	else:
		context.report_html = (
			"<div style='padding:24px;font-family:sans-serif'>"
			"<h1>Informe cobranza</h1>"
			"<p>Aún no hay un informe generado. Ejecutá el import de cobranza o el import roster "
			"y volvé a abrir esta página.</p>"
			"</div>"
		)
