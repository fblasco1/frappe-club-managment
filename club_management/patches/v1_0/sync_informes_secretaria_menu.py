"""Sincroniza menú de informes: Cobranza por fechas, Pagos por equipo, Deuda por actividad."""

from __future__ import annotations

import frappe

from club_management.activities.setup.actividades_workspace_sidebar import (
	sync_actividades_workspace_sidebar,
)
from club_management.members.setup.inicio_workspace import CLUB_DESK_REPORTS
from club_management.members.setup.secretaria_workspace_sidebar import (
	sync_secretaria_workspace_sidebar,
)

LEGACY_TO_CANONICAL = {
	"Recaudacion por concepto": "Cobranza por fechas",
	"Pagos del dia": "Cobranza por fechas",
}

RETIRED_FROM_MENU = frozenset(
	{
		"Pagos del dia",
		"Recaudacion por concepto",
		"Deuda por equipo",
	}
)


def _retarget_report_links() -> None:
	for old_name, new_name in LEGACY_TO_CANONICAL.items():
		if not frappe.db.exists("Report", new_name):
			continue
		for doctype in ("Workspace Link", "Workspace Sidebar Item"):
			for row in frappe.get_all(
				doctype,
				filters={"link_type": "Report", "link_to": old_name},
				fields=["name"],
			):
				frappe.db.set_value(
					doctype,
					row.name,
					{"link_to": new_name, "label": new_name},
					update_modified=False,
				)


def _remove_retired_menu_links() -> None:
	for report_name in RETIRED_FROM_MENU:
		if report_name in CLUB_DESK_REPORTS:
			continue
		for doctype in ("Workspace Link", "Workspace Sidebar Item"):
			frappe.db.delete(
				doctype,
				{
					"link_type": "Report",
					"link_to": report_name,
				},
			)


def execute() -> None:
	_retarget_report_links()
	_remove_retired_menu_links()
	sync_secretaria_workspace_sidebar()
	sync_actividades_workspace_sidebar()
	frappe.clear_cache(doctype="Workspace")
	frappe.clear_cache(doctype="Workspace Sidebar")
	frappe.clear_cache(doctype="Report")
