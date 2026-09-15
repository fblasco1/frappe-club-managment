"""Workspaces Desk del club: navegación y defaults para Secretaría."""

from __future__ import annotations

import json

import frappe

INICIO_WORKSPACE_NAME = "Inicio"
LEGACY_INICIO_WORKSPACE_NAME = "Inicio Club"
GESTION_ACTIVIDADES_WORKSPACE_NAME = "Gestión de Actividades"
SECRETARIA_WORKSPACE_NAME = "Secretaría"

CLUB_DESK_NAV_TABS: list[tuple[str, str]] = [
	("Gestión de Socios", SECRETARIA_WORKSPACE_NAME),
	("Gestión de Actividades", GESTION_ACTIVIDADES_WORKSPACE_NAME),
]

CLUB_DESK_REPORTS: tuple[str, ...] = (
	"Cobranza por fechas",
	"Pagos por equipo",
	"Deuda por actividad",
)

# Informes retirados del menú (aliases / absorbidos).
CLUB_DESK_REPORTS_LEGACY: tuple[str, ...] = (
	"Recaudacion por concepto",
	"Pagos del dia",
	"Deuda por equipo",
)

RETIRED_INICIO_CONTENT: list[dict] = []


def set_secretaria_role_home_page() -> None:
	"""Página Desk inicial: landing con Socios / Actividades / Configuración."""
	if not frappe.db.exists("Role", "Secretaria"):
		return

	frappe.db.set_value(
		"Role",
		"Secretaria",
		"home_page",
		"/desk",
		update_modified=False,
	)


def set_secretaria_default_workspace(*, only_if_empty: bool = False) -> int:
	"""Asigna `default_workspace` = Secretaría a usuarios Secretaría."""
	if not frappe.db.exists("Workspace", SECRETARIA_WORKSPACE_NAME):
		return 0

	updated = 0
	for user_name in _secretaria_user_names():
		current = frappe.db.get_value("User", user_name, "default_workspace")
		if only_if_empty and current and current not in (
			None,
			"",
			LEGACY_INICIO_WORKSPACE_NAME,
			INICIO_WORKSPACE_NAME,
		):
			continue
		frappe.db.set_value(
			"User",
			user_name,
			"default_workspace",
			SECRETARIA_WORKSPACE_NAME,
			update_modified=False,
		)
		updated += 1
	return updated


def retire_inicio_workspace() -> None:
	"""Oculta Inicio y deja de usarlo como landing."""
	if frappe.db.exists("Workspace", LEGACY_INICIO_WORKSPACE_NAME) and not frappe.db.exists(
		"Workspace", INICIO_WORKSPACE_NAME
	):
		frappe.rename_doc("Workspace", LEGACY_INICIO_WORKSPACE_NAME, INICIO_WORKSPACE_NAME, force=True)

	if frappe.db.exists("Workspace", INICIO_WORKSPACE_NAME):
		ws = frappe.get_doc("Workspace", INICIO_WORKSPACE_NAME)
		ws.is_hidden = 1
		ws.content = json.dumps(RETIRED_INICIO_CONTENT)
		ws.shortcuts = []
		ws.save(ignore_permissions=True)

		frappe.db.sql(
			"""
			UPDATE `tabUser`
			SET default_workspace = %s
			WHERE default_workspace IN (%s, %s)
			""",
			(SECRETARIA_WORKSPACE_NAME, INICIO_WORKSPACE_NAME, LEGACY_INICIO_WORKSPACE_NAME),
		)

	_clear_inicio_parent_links()


def _clear_inicio_parent_links() -> None:
	"""Quita `parent_page` = Inicio en workspaces operativos del club."""
	for workspace_name in (SECRETARIA_WORKSPACE_NAME, GESTION_ACTIVIDADES_WORKSPACE_NAME):
		if not frappe.db.exists("Workspace", workspace_name):
			continue
		parent = frappe.db.get_value("Workspace", workspace_name, "parent_page")
		if parent in (INICIO_WORKSPACE_NAME, LEGACY_INICIO_WORKSPACE_NAME, None, ""):
			frappe.db.set_value(
				"Workspace",
				workspace_name,
				"parent_page",
				"",
				update_modified=False,
			)


def migrate_legacy_inicio_workspace() -> None:
	"""Compatibilidad: renombra Inicio Club y retira landing."""
	retire_inicio_workspace()


def _secretaria_user_names() -> list[str]:
	return frappe.db.sql(
		"""
		SELECT DISTINCT hr.parent
		FROM `tabHas Role` hr
		INNER JOIN `tabUser` u ON u.name = hr.parent
		WHERE hr.role = %s
		  AND u.enabled = 1
		  AND u.user_type = 'System User'
		""",
		("Secretaria",),
		pluck=True,
	)
